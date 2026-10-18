from contextlib import closing
import io
import os
import uuid
import logging
import sqlite3
import threading
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Union, Literal
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from backend.services.serializer import sanitize_for_json
from backend.services.analysis_response import build_analysis_response
from backend.services.report_artifacts import report_path, REPORT_TYPES

from backend.config import (
    UPLOAD_DIR,
    REPORTS_DIR,
    CHARTS_DIR,
    NVIDIA_REASONING_MODEL,
    GROQ_REASONING_MODEL,
    GROQ_API_KEYS,
    NVIDIA_API_KEYS,
)
from backend.services.r2_service import r2_service
from backend.services.supabase_service import db_service
from backend.services.auth_service import auth_service
from backend.config import CORS_ORIGINS, AUTH_ALLOW_REGISTRATION, BASE_DIR
from backend.services.llm_service import invoke_llm, key_pool_health, routing_summary
from backend.graph.workflow import run_analyst_pipeline
from backend.graph.state import AgentState
from backend.tools.python_tool import execute_python
from backend.tools.sql_tool import execute_sql
# ── Architectural Improvements & Extended ML Services ─────────────────────────
from backend.services.profiler import profile_dataset           # Improvement #1
from backend.services.job_queue import job_queue, QueueFullError
from backend.services.session_store import session_store, SessionLimitError
from backend.services.upload_limits import read_upload, parse_upload, validate_dataset_size, UploadBodyLimitMiddleware
from backend.config import MAX_CACHED_SESSIONS
from backend.services.cleaner import clean_dataset, clean_column_names, strip_column_names
from backend.services.automl_engine import run_automl, predict_with_saved_model, detect_target_and_task, validate_automl_input
from backend.services.dataset_views import active_dataframe, model_dataframe
from backend.services.experiment_tracker import log_experiment, get_project_experiments, compute_dataset_hash

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app):
    job_queue.recover({'analysis': resume_analysis_job, 'automl': resume_automl_job, 'forecast': resume_forecast_job, 'text': resume_text_job})
    yield


app = FastAPI(
    title="📊 Autonomous AI Data Analyst Agent API",
    description="Autonomous Agentic Business Intelligence & Diagnostic Engine powered by Groq, NVIDIA NIM, and Deterministic Analytics.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(UploadBodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active session cache
active_sessions = OrderedDict()
session_cache_lock = threading.RLock()

bearer = HTTPBearer(auto_error=False)


def current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    try:
        if not credentials or credentials.scheme.lower() != 'bearer':
            raise ValueError('Please sign in.')
        return auth_service.authenticate(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(401, str(exc), headers={'WWW-Authenticate': 'Bearer'}) from exc


def owned_project(project_id, user):
    # Canonical UUIDs also prevent path traversal in artifact paths.
    try:
        if str(uuid.UUID(project_id)) != project_id:
            raise ValueError()
    except ValueError:
        raise HTTPException(404, 'Project not found.')
    project = db_service.get_project(project_id)
    if not project or project['owner_id'] != user['id']:
        raise HTTPException(404, 'Project not found.')
    return project


def owned_session(project_id, user):
    owned_project(project_id, user)
    with session_cache_lock:
        session = active_sessions.get(project_id)
        if session is None:
            session = session_store.load(project_id, user['id'])
            if session is not None:
                cache_session(project_id, session, persist=False)
        if not session:
            raise HTTPException(404, 'Dataset session unavailable. Please upload the dataset again.')
        active_sessions.move_to_end(project_id)
        return session


def cache_session(project_id, session, persist=True):
    if persist:
        session_store.save(project_id, session)
    with session_cache_lock:
        active_sessions[project_id] = session
        active_sessions.move_to_end(project_id)
        while len(active_sessions) > MAX_CACHED_SESSIONS:
            active_sessions.popitem(last=False)


def register_session(project_id, session, user):
    validate_dataset_size(session['df'])
    session['owner_id'] = user['id']
    session['revision'] = 0
    try:
        session_store.save(project_id, session)
    except SessionLimitError as exc:
        raise HTTPException(429, str(exc)) from exc
    db_service.save_project(session['dataset_name'], '', project_id=project_id, owner_id=user['id'])
    cache_session(project_id, session, persist=False)


def submit_job(**kwargs):
    try:
        return job_queue.submit(**kwargs)
    except QueueFullError as exc:
        raise HTTPException(429, str(exc), headers={'Retry-After': '30'}) from exc


def job_session(project_id, owner_id, payload):
    session = owned_session(project_id, {'id': owner_id})
    if session.get('revision', 0) != payload.get('revision', 0):
        raise ValueError('Dataset changed since submission. Submit a new job.')
    return session


def execute_analysis_job(project_id, owner_id, payload, progress):
    session = job_session(project_id, owner_id, payload)
    initial = dict(project_id=project_id, owner_id=owner_id,
        dataset_name=session.get('dataset_name', 'Dataset'), df_raw=active_dataframe(session).copy(),
        user_question=payload.get('user_question') or session.get('user_question'),
        execution_steps=[], errors=[], _progress_callback=progress)
    result = run_analyst_pipeline(initial)
    result.pop('_progress_callback', None)
    session['analysis'] = result
    cache_session(project_id, session)
    return build_analysis_response(project_id, result, REPORTS_DIR)


def execute_automl_job(project_id, owner_id, payload, progress):
    session = job_session(project_id, owner_id, payload)
    workspace_store.ensure(session)
    df, target, clip = model_dataframe(session, payload.get('target_column'))
    result = run_automl(df=df, target_column=target, project_id=project_id,
        run_tuning=payload.get('run_tuning', True), task_type=payload.get('task_type'),
        clip_outliers=clip, progress_callback=progress, split_strategy=payload.get("split_strategy","random"),
        group_column=payload.get("group_column"),date_column=payload.get("date_column"),holdout_fraction=payload.get("holdout_fraction",.2),
        include_columns=payload.get('include_columns'),selection_percentile=payload.get('selection_percentile',100),compare_features=payload.get('compare_features',False))
    result = sanitize_for_json(result)
    result = workspace_store.save_run(session,result,'automl',payload)
    session['automl'], session['model_invalidated'] = result, False
    cache_session(project_id, session)
    best = result.get('best_model', {})
    log_experiment(experiment_id=str(uuid.uuid4()), project_id=project_id,
        dataset_name=session.get('dataset_name', 'Dataset'), dataset_hash=compute_dataset_hash(df),
        target_column=result.get('target_column', ''), task_type=result.get('task_type', ''),
        best_model=best.get('model_name', 'Unknown'),
        primary_metric_name=best.get('primary_metric_name', 'r2_score'),
        primary_metric_value=best.get('primary_metric', 0), metrics=result.get('leaderboard', []),
        hyperparameters=result.get('optuna_tuning'), model_artifact_path=result.get('saved_model_path'))
    return result


resume_analysis_job = execute_analysis_job
resume_automl_job = execute_automl_job


class Credentials(BaseModel):
    username: str
    password: str


@app.post('/api/auth/register', status_code=201)
def register_account(credentials: Credentials):
    if not AUTH_ALLOW_REGISTRATION:
        raise HTTPException(403, 'Account registration is disabled.')
    try:
        return auth_service.register(credentials.username, credentials.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/auth/login')
def login_account(credentials: Credentials):
    if len(credentials.username)>64 or len(credentials.password)>128:
        raise HTTPException(401, 'Invalid username or password.')
    try:
        return auth_service.login(credentials.username, credentials.password)
    except PermissionError as exc:
        raise HTTPException(429, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc


@app.get('/api/auth/me')
def account_details(user=Depends(current_user)):
    return {'id': user['id'], 'username': user['username']}


@app.post('/api/auth/logout')
def logout_account(user=Depends(current_user)):
    auth_service.logout(user['session_id'])
    return {'status': 'signed_out'}


class AnalyzeRequest(BaseModel):
    project_id: str
    user_question: Optional[str] = None


class ChatRequest(BaseModel):
    project_id: str
    message: str


class CleanRequest(BaseModel):
    project_id: str
    target_column: Optional[str] = None
    handle_missing: bool = True
    handle_outliers: bool = True
    remove_duplicates: bool = True
    standardize_names: bool = True


class AutoMLRequest(BaseModel):
    project_id: str
    target_column: Optional[str] = None
    run_tuning: bool = True
    task_type: Optional[Literal['classification', 'regression']] = None
    split_strategy: Literal['random','grouped','chronological'] = 'random'
    group_column: Optional[str] = None
    date_column: Optional[str] = None
    holdout_fraction: float = .2
    include_columns: Optional[List[str]] = None
    selection_percentile: int = Field(default=100,ge=1,le=100)
    compare_features: bool = False


class PredictRequest(BaseModel):
    project_id: str
    input_data: Union[Dict[str, Any], List[Dict[str, Any]]]


@app.get("/")
def root(user=Depends(current_user)):
    return {
        "status": "online",
        "service": "Autonomous AI Data Analyst Agent",
        "groq_keys_active": len(GROQ_API_KEYS),
        "nvidia_keys_active": len(NVIDIA_API_KEYS),
        "primary_model": "task-specific",
        "llm_task_routes": routing_summary(),
        "gemini_keys_active": len(key_pool_health()['gemini']['keys']),
        "alternative_120b": GROQ_REASONING_MODEL,
        "capabilities": [
            "Semantic Schema Profiling",
            "Data Health Audit (0-100 Score)",
            "Automated Domain KPI Modeling",
            "Root-Cause & Pareto 80/20 Diagnostics",
            "Statistical Hypothesis Testing (p-values)",
            "Interactive Plotly Dashboards",
            "Executive Storytelling & Action Plans",
        ],
    }


@app.get("/api/sample-datasets")
def get_sample_datasets(user=Depends(current_user)):
    """Returns business datasets tailored for analytical exploration."""
    return [
        {
            "id": "ecommerce_sales",
            "name": "E-Commerce Global Retail",
            "domain": "Retail & E-Commerce",
            "description": "Transactions across regions, categories, sales, discounts, and profits.",
        },
        {
            "id": "saas_churn",
            "name": "SaaS Customer Subscriptions",
            "domain": "Subscription & SaaS",
            "description": "Monthly recurring revenue, contract type, tenure, support calls, and churn.",
        },
        {
            "id": "ops_fulfillment",
            "name": "Supply Chain & Fulfillment",
            "domain": "Operations & Logistics",
            "description": "Shipping modes, lead time, delivery status, shipping cost, and SLA breaches.",
        },
    ]


@app.post("/api/load-sample")
def load_sample_dataset(sample_id: str = Form(...), user=Depends(current_user)):
    """Generates and loads a realistic business benchmark dataset."""
    project_id = str(uuid.uuid4())
    import numpy as np

    if sample_id not in {"ecommerce_sales", "saas_churn", "ops_fulfillment"}:
        raise HTTPException(400, "Unknown sample dataset.")
    rng = np.random.default_rng(42)
    n_rows = 600

    if sample_id == "saas_churn":
        dataset_name = "SaaS Subscriptions & Churn"
        tiers = ["Starter", "Professional", "Enterprise"]
        regions = ["North America", "EMEA", "APAC", "LATAM"]
        dates = pd.date_range(start="2025-01-01", periods=12, freq="ME")
        
        df = pd.DataFrame({
            "customer_id": [f"CUST-{1000+i}" for i in range(n_rows)],
            "signup_date": rng.choice(dates, size=n_rows),
            "tier": rng.choice(tiers, size=n_rows, p=[0.5, 0.35, 0.15]),
            "region": rng.choice(regions, size=n_rows, p=[0.45, 0.3, 0.15, 0.1]),
            "mrr": rng.choice([29, 99, 499], size=n_rows, p=[0.5, 0.35, 0.15]) + rng.uniform(-5, 15, n_rows).round(2),
            "support_tickets": rng.poisson(lam=2.5, size=n_rows),
            "nps_score": rng.integers(1, 11, size=n_rows),
            "churned": rng.choice(["Yes", "No"], size=n_rows, p=[0.18, 0.82]),
        })
    elif sample_id == "ops_fulfillment":
        dataset_name = "Supply Chain & Fulfillment"
        modes = ["Standard", "Express", "Same Day", "Freight"]
        warehouses = ["WH-East", "WH-West", "WH-Central", "WH-South"]
        df = pd.DataFrame({
            "order_id": [f"ORD-{5000+i}" for i in range(n_rows)],
            "order_date": pd.date_range(start="2025-01-01", periods=120, freq="D").repeat(5)[:n_rows],
            "shipping_mode": rng.choice(modes, size=n_rows, p=[0.5, 0.3, 0.1, 0.1]),
            "warehouse": rng.choice(warehouses, size=n_rows),
            "transit_days": rng.normal(loc=4.2, scale=1.5, size=n_rows).clip(1, 14).round(1),
            "shipping_cost": rng.exponential(scale=25, size=n_rows).round(2) + 5,
            "sla_breach": rng.choice([0, 1], size=n_rows, p=[0.88, 0.12]),
        })
    else:  # ecommerce_sales
        dataset_name = "E-Commerce Global Retail"
        regions = ["North America", "Europe", "Asia", "Latin America"]
        categories = ["Electronics", "Furniture", "Office Supplies", "Apparel"]
        dates = pd.date_range(start="2025-01-01", periods=12, freq="ME").repeat(50)[:n_rows]
        
        df = pd.DataFrame({
            "order_id": [f"SO-{20000+i}" for i in range(n_rows)],
            "order_date": dates,
            "region": rng.choice(regions, size=n_rows, p=[0.4, 0.3, 0.2, 0.1]),
            "category": rng.choice(categories, size=n_rows, p=[0.35, 0.25, 0.25, 0.15]),
            "sales": rng.exponential(scale=180, size=n_rows).round(2) + 10,
            "quantity": rng.integers(1, 10, size=n_rows),
            "discount": rng.choice([0.0, 0.1, 0.15, 0.2, 0.3], size=n_rows),
            "profit": rng.normal(loc=35, scale=40, size=n_rows).round(2),
        })

    # Cache in session
    register_session(project_id, {
        "project_id": project_id,
        "dataset_name": dataset_name,
        "df": df,
        "user_question": None,
    }, user)

    return sanitize_for_json({
        "project_id": project_id,
        "dataset_name": dataset_name,
        "columns": df.columns.tolist(),
        "preview": df.head(10).to_dict(orient="records"),
        "shape": {"rows": df.shape[0], "columns": df.shape[1]},
        "profile": profile_dataset(df, dataset_name=dataset_name),
    })


@app.post("/api/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    user_question: Optional[str] = Form(None),
    user=Depends(current_user),
):
    """Uploads CSV or Excel dataset for analytical audit."""
    project_id = str(uuid.uuid4())
    dataset_name = (file.filename or "Dataset.csv").rsplit(".", 1)[0]
    contents = await read_upload(file)
    df = parse_upload(contents, file.filename)

    register_session(project_id, {
        "project_id": project_id,
        "dataset_name": dataset_name,
        "df": df,
        "user_question": user_question,
    }, user)

    return JSONResponse(content=sanitize_for_json({
        "project_id": project_id,
        "dataset_name": dataset_name,
        "columns": df.columns.tolist(),
        "preview": df.head(10).to_dict(orient="records"),
        "shape": {"rows": df.shape[0], "columns": df.shape[1]},
    }))


@app.post("/api/analyze")
def analyze_dataset(request: AnalyzeRequest, user=Depends(current_user)):
    """Runs the Autonomous AI Data Analyst pipeline."""
    project_id = request.project_id
    session = owned_session(project_id, user)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found. Please upload dataset first.")

    initial_state: AgentState = {
        "project_id": project_id,
        "dataset_name": session.get("dataset_name", "Dataset"),
        "df_raw": active_dataframe(session).copy(),
        "owner_id": user["id"],
        "user_question": request.user_question or session.get("user_question"),
        "execution_steps": [],
        "errors": [],
    }

    final_state = run_analyst_pipeline(initial_state)
    session["analysis"] = final_state
    cache_session(project_id, session)

    return JSONResponse(content=build_analysis_response(project_id, final_state, REPORTS_DIR))


@app.get('/api/datasets/{project_id}/download')
def download_dataset(project_id: str, user=Depends(current_user)):
    from fastapi.responses import Response
    session = owned_session(project_id, user)
    return Response(active_dataframe(session).to_csv(index=False), media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="dataset_{project_id}.csv"'})


@app.get('/api/projects')
def list_owned_projects(user=Depends(current_user)):
    with closing(sqlite3.connect(db_service.local_db_path)) as conn, conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''SELECT p.id,p.name,p.created_at,s.updated_at,
            (s.project_id IS NOT NULL) AS session_available FROM projects p
            LEFT JOIN dataset_sessions s ON s.project_id=p.id
            WHERE p.owner_id=? ORDER BY COALESCE(s.updated_at,p.created_at) DESC''', (user['id'],)).fetchall()
    return [dict(row) for row in rows]


@app.get('/api/projects/{project_id}/session')
def restore_project_session(project_id: str, user=Depends(current_user)):
    session = owned_session(project_id, user)
    workspace_store.ensure(session)
    cache_session(project_id,session)
    automl = dict(session.get('automl') or {})
    automl.pop('saved_model_path', None)
    return sanitize_for_json(dict(project_id=project_id, dataset_name=session['dataset_name'],
        profile=profile_dataset(active_dataframe(session), dataset_name=session['dataset_name']),
        analysis=build_analysis_response(project_id, session['analysis'], REPORTS_DIR) if session.get('analysis') else None,
        automl=automl or None, revision=session.get('revision',0),active_version_id=session.get('active_version_id'), messages=session.get('chat_messages', []),
        jobs=job_queue.latest_for_project(project_id)))


@app.delete('/api/projects/{project_id}')
def remove_project(project_id: str, user=Depends(current_user)):
    owned_project(project_id, user)
    if job_queue.has_pending(project_id):
        raise HTTPException(409, 'Wait for current work to finish before removing this project.')
    session_store.delete(project_id, user['id'])
    active_sessions.pop(project_id, None)
    with closing(sqlite3.connect(db_service.local_db_path)) as conn, conn:
        for table in ('reports', 'chat_messages', 'model_leaderboard', 'experiments','dataset_versions','workspace_runs','cleaning_audits','prediction_batches'):
            if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone():
                conn.execute(f'DELETE FROM {table} WHERE project_id=?', (project_id,))
        conn.execute('DELETE FROM projects WHERE id=? AND owner_id=?', (project_id, user['id']))
    return {'status': 'removed', 'project_id': project_id}


@app.post("/api/chat")
def conversational_analyst_chat(request: ChatRequest, user=Depends(current_user)):
    """
    Conversational Data Analyst:
    Answers ad-hoc business questions. Executes Python/SQL calculations dynamically
    to verify numerical answers and prevent hallucinations.
    """
    project_id = request.project_id
    user_query = request.message
    session = owned_session(project_id, user)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found.")

    df: pd.DataFrame = active_dataframe(session)
    analysis = session.get("analysis", {})

    session.setdefault('chat_messages', []).append(dict(role='user', content=user_query))
    cache_session(project_id, session)
    db_service.save_chat_message(project_id, "user", user_query)

    # 1. Ask LLM if calculation code is required
    planning_prompt = f"""You are an Autonomous AI Data Analyst.
A user asked: "{user_query}"
Dataset Columns: {list(df.columns)}
Dataset Sample: {df.head(2).to_dict(orient='records')}

If answering this requires a calculation (aggregations, sums, percentages, group-by, delta, filter),
generate short pandas expressions and simple assignments (dataset is 'df'; assign final output to 'result').
Supported methods include sum, mean, median, min, max, count, std, quantile, nunique, value_counts, groupby, agg, head, sort_values, round, corr, select_dtypes, isna, notna, duplicated, drop_duplicates, stack, reset_index and to_dict. Use numeric_only=True for correlation. When ranking correlations with a target, exclude the target itself using drop(target_name) before sorting by absolute correlation. Keep output below 1000 rows with head().
Do not use imports, loops, functions, comprehensions, file operations, apply, eval or query.
If no calculation is needed, respond with "NO_CODE".

Respond ONLY with executable Python code or "NO_CODE"."""

    # Basic dataset-count requests need no model decision or generated arithmetic.
    question = user_query.lower()
    dataset_counts = all(word in question for word in ('row', 'column', 'duplicate', 'missing')) and any(
        word in question for word in ('count', 'how many'))
    code_plan = ("result = {'Total rows': df.shape[0], 'Total columns': df.shape[1], "
                 "'Duplicate rows': int(df.duplicated().sum()), "
                 "'Missing cells': int(df.isna().sum().sum())}" if dataset_counts else
                 invoke_llm(planning_prompt, tier="fast", task="chat_code", temperature=0.1).strip())

    calc_evidence = None
    calculation_error = None
    execution_status = "not_requested"
    code_requested = "NO_CODE" not in code_plan
    if code_requested:
        py_res = execute_python(code_plan, df)
        if not py_res["success"]:
            repair_prompt = f"""{planning_prompt}
The previous analytical expression failed: {py_res['error']}
Previous expression: {code_plan}
Rewrite it using ONLY the supported expressions. Do not assign attributes or indexes.
Use df.duplicated().sum() for duplicate counts and df.corr(numeric_only=True) for correlations.
Assign output to result. Return only code."""
            try:
                repaired = invoke_llm(repair_prompt, tier="fast", task="chat_code", temperature=0.0).strip()
                if "NO_CODE" not in repaired:
                    code_plan = repaired
                    py_res = execute_python(code_plan, df)
            except Exception:
                pass
        if py_res["success"]:
            execution_status = "succeeded"
            calc_evidence = py_res["result"] if py_res["result"] is not None else py_res["stdout"]
        else:
            execution_status = "failed"
            calculation_error = py_res["error"]

    # Failed calculations never become evidence or trigger a speculative numerical answer.
    if execution_status == "failed":
        ai_reply = ("I couldn’t verify this calculation. No numerical conclusion has been produced. "
                    "Try a simpler question, such as the duplicate count or a single column’s average.")
    elif dataset_counts:
        ai_reply = "| Metric | Count |\n| --- | ---: |\n" + "\n".join(
            f"| {label} | {value} |" for label, value in calc_evidence.items())
    else:
        system_prompt = ("You are a careful data analyst. Use only the supplied calculated evidence and context. "
            "Never invent numerical values, benchmarks, currency symbols, periods or causal explanations. "
            "Distinguish observations from hypotheses. If evidence is insufficient, say what is unknown. "
            "Do not claim a calculation succeeded unless execution_status is succeeded. "
            "A correlation does not establish causation. Display coefficients to four decimal places while retaining exact evidence. Format answers in concise Markdown.")
        context = f"""
Dataset: {session.get('dataset_name')}
Data Health Score: {analysis.get('health_score', 'Not available')}
Columns: {list(df.columns)}
Diagnostic Summary: {analysis.get('diagnostic_results', {}).get('diagnostic_narrative', 'Not available')}
execution_status: {execution_status}
Calculated Evidence: {calc_evidence if calc_evidence is not None else 'No calculation was performed. Do not provide unverified numbers.'}
"""
        answer_prompt = f"Context:\n{context}\nUser Question: {user_query}\nAnswer using only this evidence."
        ai_reply = invoke_llm(answer_prompt, system_prompt=system_prompt, tier="reasoning", task="chat_answer", temperature=0.0)

    # Save to Supabase
    db_service.save_chat_message(project_id, "assistant", ai_reply)
    session['chat_messages'].append(dict(role='assistant', content=ai_reply,
        code=code_plan if 'NO_CODE' not in code_plan else None,
        evidence=str(calc_evidence) if calc_evidence is not None else None,
        execution_status=execution_status, calculation_error=calculation_error))
    cache_session(project_id, session)

    return {
        "project_id": project_id,
        "reply": ai_reply,
        "code_executed": code_plan if "NO_CODE" not in code_plan else None,
        "calculated_evidence": str(calc_evidence) if calc_evidence is not None else None,
        "execution_status": execution_status,
        "calculation_error": calculation_error,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT #1: Deterministic Dataset Profiling (no LLM, instant response)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/profile")
async def profile_uploaded_dataset(file: UploadFile = File(...), user=Depends(current_user)):
    """
    Fast deterministic profiling — returns column types, missing values,
    outliers, distributions, quality score, and correlation matrix.
    No LLM calls — instant response (typically <2s for datasets up to 100k rows).
    Also caches the dataset for follow-up /api/analyze/start.
    """
    contents = await read_upload(file)
    dataset_name = (file.filename or "Dataset.csv").rsplit(".", 1)[0]
    df = parse_upload(contents, file.filename)

    project_id = str(uuid.uuid4())
    register_session(project_id, {
        "project_id": project_id,
        "dataset_name": dataset_name,
        "df": df,
        "user_question": None,
    }, user)

    profile = profile_dataset(df, dataset_name=dataset_name)
    return JSONResponse(content=sanitize_for_json({"project_id": project_id, **profile}))


@app.get("/api/profile/{project_id}")
def get_profile(project_id: str, user=Depends(current_user)):
    """Re-run profiling on an already-uploaded dataset session."""
    session = owned_session(project_id, user)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found.")
    profile = profile_dataset(active_dataframe(session), dataset_name=session.get("dataset_name", "Dataset"))
    return JSONResponse(content=sanitize_for_json(profile))


# ═══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT #2: Background Job Queue for Long-Running AI Analysis
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/analyze/start")
def start_analysis_job(request: AnalyzeRequest, user=Depends(current_user)):
    """
    Starts the full AI analysis pipeline as a background job.
    Returns immediately with job_id. Poll /api/job/{job_id}/status.
    """
    project_id = request.project_id
    session = owned_session(project_id, user)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found. Upload dataset first.")

    def _run_pipeline(**kwargs):
        return execute_analysis_job(project_id, user['id'], payload, kwargs.get('_progress_callback'))

    payload = dict(user_question=request.user_question, revision=session.get('revision', 0))
    job_id = submit_job(project_id=project_id, fn=_run_pipeline, owner_id=user['id'],
        kind='analysis', payload=payload, on_progress=True)

    return {
        "job_id": job_id,
        "project_id": project_id,
        "status": "queued",
        "poll_url": f"/api/job/{job_id}/status",
        "result_url": f"/api/job/{job_id}/result",
    }


@app.get("/api/job/{job_id}/status")
def get_job_status(job_id: str, user=Depends(current_user)):
    """Poll background job status. Returns progress 0-100 and current step name."""
    status = job_queue.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found.")
    owned_project(status['project_id'], user)
    return JSONResponse(content=sanitize_for_json(status))


@app.get("/api/job/{job_id}/result")
def get_job_result(job_id: str, user=Depends(current_user)):
    """Retrieve completed analysis result once job_status == 'completed'."""
    status = job_queue.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found.")
    owned_project(status['project_id'], user)
    if status["status"] != "completed":
        raise HTTPException(
            status_code=202,
            detail=f"Job not completed. Status: {status['status']} ({status['progress']}%)"
        )
    result = job_queue.get_result(job_id)
    if not result:
        raise HTTPException(status_code=500, detail="Result missing despite completed status.")
    return JSONResponse(content=sanitize_for_json(result))


# ═══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT #4: API Key Pool Health Monitoring
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/keys/health")
def get_key_pool_health(user=Depends(current_user)):
    """Observe the exact pools used by this API process's LLM calls."""
    return key_pool_health()


# ═══════════════════════════════════════════════════════════════════════════════
# INTELLIGENT DATA CLEANING ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/clean")
def clean_project_dataset(request: CleanRequest, user=Depends(current_user)):
    """Cleans dataset and updates session DataFrame with audit trail."""
    project_id = request.project_id
    session = owned_session(project_id, user)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found.")

    if job_queue.has_pending(project_id):
        raise HTTPException(409, "Wait for this project's current job before cleaning its dataset.")
    df_raw = session["df"]
    options = {key: getattr(request, key) for key in
        ('handle_missing', 'handle_outliers', 'remove_duplicates', 'standardize_names')}
    target_source = request.target_column or session.get('cleaning_target_source') or session.get('automl', {}).get('target_column')
    try:
        if request.target_column is not None and session.get('cleaning_options', {}).get('standardize_names'):
            _, mapping = clean_column_names(df_raw)
            target_source = {new: old for old, new in mapping.items()}.get(target_source, target_source)
        cleaned_df, audit_log = clean_dataset(df_raw, target_column=target_source, **options)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    workspace_store.ensure(session)
    session['active_version_id']=workspace_store.add_version(session,cleaned_df,'Automatic cleaning',[dict(operation='automatic_cleaning',audit=audit_log)],session['active_version_id'])
    # Update active session with cleaned dataframe
    session["df_cleaned"] = cleaned_df
    session["cleaning_audit"] = audit_log
    session['cleaning_options'] = options
    session['cleaning_target_source'] = target_source
    session.pop('analysis', None)
    session.pop('automl', None)
    session['model_invalidated'] = True
    session['revision'] = session.get('revision', 0) + 1
    cache_session(project_id, session)

    return JSONResponse(content=sanitize_for_json({
        "project_id": project_id,
        "audit_log": audit_log,
        "preview": cleaned_df.head(10).to_dict(orient="records"),
        "shape": {"rows": cleaned_df.shape[0], "columns": cleaned_df.shape[1]},
        "columns": cleaned_df.columns.tolist(),
        "profile": profile_dataset(cleaned_df, dataset_name=session.get('dataset_name', 'Dataset')),
    }))


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-ALGORITHM AUTOML ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/automl/start")
def start_automl_training(request: AutoMLRequest, user=Depends(current_user)):
    """
    Submits an AutoML competition background job:
    Trains multiple models, tunes with Optuna, computes SHAP XAI, and builds leaderboard.
    """
    project_id = request.project_id
    session = owned_session(project_id, user)
    if job_queue.has_pending(project_id):
        raise HTTPException(429, 'This project already has queued or running work.', headers={'Retry-After': '30'})
    if not session:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        df_to_use, target, clip_outliers = model_dataframe(session, request.target_column)
        target, _, _ = validate_automl_input(df_to_use, target, request.task_type)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    # If a different label is selected after cleaning, rebuild the analytical
    # view from source so that label's missing values and outliers stay intact.
    if session.get('cleaning_options'):
        options = session['cleaning_options']
        source_target = target
        if options['standardize_names']:
            _, mapping = clean_column_names(session['df'])
            source_target = next(old for old, new in mapping.items() if new == target)
        if source_target != session.get('cleaning_target_source'):
            session['df_cleaned'], session['cleaning_audit'] = clean_dataset(
                session['df'], target_column=source_target, **options)
            session['cleaning_target_source'] = source_target
            session.pop('analysis', None)
            session['revision'] = session.get('revision', 0) + 1
    dataset_name = session.get("dataset_name", "Dataset")

    cache_session(project_id, session)
    workspace_store.ensure(session)
    payload = dict(target_column=target, task_type=request.task_type,split_strategy=request.split_strategy,group_column=request.group_column,date_column=request.date_column,holdout_fraction=request.holdout_fraction,
        run_tuning=request.run_tuning, revision=session.get('revision', 0),include_columns=request.include_columns,
        selection_percentile=request.selection_percentile,compare_features=request.compare_features)
    def _train_automl_job(**kwargs):
        return execute_automl_job(project_id, user['id'], payload, kwargs.get('_progress_callback'))
    job_id = submit_job(project_id=project_id, fn=_train_automl_job, owner_id=user['id'],
        kind='automl', payload=payload, on_progress=True)

    return {
        "job_id": job_id,
        "project_id": project_id,
        "status": "queued",
        "poll_url": f"/api/job/{job_id}/status",
        "result_url": f"/api/job/{job_id}/result",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WHAT-IF SIMULATION & PREDICTION API
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/predict")
def predict_endpoint(request: PredictRequest, user=Depends(current_user)):
    """Generates predictions using the best trained model pipeline for a project."""
    project_id = request.project_id
    owned_project(project_id, user)
    session = active_sessions.get(project_id) or session_store.load(project_id, user['id'])
    automl_res = session.get("automl") if session else None
    if session and session.get('model_invalidated'):
        raise HTTPException(409, 'Dataset changed. Retrain the model before prediction.')

    model_path = None
    if automl_res:
        model_path = automl_res.get("saved_model_path")
    else:
        # Check default path
        candidate_dir = BASE_DIR / 'artifacts' / 'models' / project_id
        if os.path.exists(candidate_dir):
            files = [os.path.join(candidate_dir, f) for f in os.listdir(candidate_dir) if f.endswith(".joblib")]
            files.sort(key=lambda path: (os.path.basename(path)=="champion.joblib", os.path.getmtime(path)), reverse=True)
            if files:
                model_path = files[0]

    if not model_path or not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail="No trained model found for this project. Run AutoML first.")

    try:
        preds = predict_with_saved_model(model_path, request.input_data)
        return JSONResponse(content=sanitize_for_json(preds))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prediction error: {e}")


@app.get("/api/models/{project_id}/download")
def download_model_artifact(project_id: str, user=Depends(current_user)):
    """Downloads the trained model pipeline (.joblib)."""
    owned_project(project_id, user)
    session = active_sessions.get(project_id) or session_store.load(project_id, user['id'])
    if session and session.get('model_invalidated'):
        raise HTTPException(409, 'Dataset changed. Retrain the model before downloading it.')
    model_path=(session.get('automl') or {}).get('saved_model_path') if session else None
    if model_path and os.path.isfile(model_path):
        return FileResponse(model_path,filename='champion.joblib',media_type='application/octet-stream')
    candidate_dir = BASE_DIR / 'artifacts' / 'models' / project_id
    if not os.path.exists(candidate_dir):
        raise HTTPException(status_code=404, detail="No model artifact found for project.")

    files = [os.path.join(candidate_dir, f) for f in os.listdir(candidate_dir) if f.endswith(".joblib")]
    files.sort(key=lambda path: (os.path.basename(path)=="champion.joblib", os.path.getmtime(path)), reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail="No model artifact found.")

    return FileResponse(
        path=files[0],
        filename=os.path.basename(files[0]),
        media_type="application/octet-stream",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# EXPERIMENT TRACKING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/experiments")
def get_all_experiments(user=Depends(current_user)):
    """Returns all tracked experiments across projects."""
    return get_project_experiments(owner_id=user['id'])


@app.get('/api/reports/{project_id}/{format}/download')
def download_report(project_id: str, format: str, user=Depends(current_user)):
    owned_project(project_id, user)
    try:
        path = report_path(project_id, format, REPORTS_DIR)
    except ValueError as exc:
        raise HTTPException(404, 'Report not found.') from exc
    if not path.is_file():
        raise HTTPException(404, 'Report not generated. Run analysis first.')
    return FileResponse(path, filename=path.name, media_type=REPORT_TYPES[format][1])


@app.get("/api/experiments/{project_id}")
def get_experiments_for_project(project_id: str, user=Depends(current_user)):
    """Returns all tracked experiments for a given project."""
    owned_project(project_id, user)
    return get_project_experiments(project_id, owner_id=user['id'])


from backend.workspace_api import install as install_workspace, workspace_store
install_workspace(app, globals())

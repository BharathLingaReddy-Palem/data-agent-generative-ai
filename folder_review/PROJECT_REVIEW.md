> **Historical snapshot from 8 October 2026.** Inventory counts and findings describe the original review, before subsequent fixes. For current behavior, regression checks and resolved issues, see [README.md](../README.md) and [FIXES.md](../FIXES.md).

# Autonomous Data Science Agent — folder review

Reviewed 8 October 2026. This is an assessment of the files currently in this folder, not a certification of the README's claims or of deployed services.

## Overall assessment

This is a substantial prototype of an automated data analysis and machine learning application. It has two user interfaces, deterministic statistics, LLM-generated interpretation, background analysis jobs, supervised AutoML, prediction, and report generation. Its strongest architectural choice is computing statistics in Python before asking an LLM to explain them.

The implementation is not ready for an exposed, multi-user production deployment. The main blockers are unrestricted execution of generated Python, missing authentication, broken project relationships, incomplete API/UI contracts, incorrect workflow dependencies, and several numerical and model-evaluation defects. Existing report and model files show that earlier runs produced artifacts; they do not prove that every current feature works correctly.

No application source, existing dataset, model, or database was changed during this review. The `folder_review` directory contains the review deliverables. A frontend verification build was written to the Windows temporary directory.

## Scope and inventory

The original folder contained **20,603 files, totaling 514.62 MB** in decimal units:

| Category | Files | Size | Review coverage |
|---|---:|---:|---|
| Project files, data, assets and generated outputs | 266 | 35.09 MB | Source and configuration review, data structure inspection, artifact metadata/text extraction, fingerprints |
| Installed JavaScript dependencies (`node_modules`) | 20,273 | 478.84 MB | Complete path/size inventory; manifests and build dependency use checked; dependency source not individually audited |
| Python bytecode caches (`__pycache__`) | 64 | 0.69 MB | Complete path/size inventory; not decompiled |

There are **56 Python files / 12,139 lines** and approximately **16,499 lines** across Python, application JavaScript/JSX/TypeScript and CSS, including comments and blanks and excluding the compiled web build. Other notable counts: 26 CSVs, 24 PDFs, 24 PowerPoint files, 26 joblib bundles, 16 pickle files including the analysis cache, and two SQLite databases.

Coverage limits are explicit: credentials were inspected by variable name and presence only; model/pickle objects were not deserialized; PDF and PowerPoint content was extracted structurally, not rendered for visual layout approval; live Groq, NVIDIA, R2 and Supabase services were not contacted. The full Python integration suite was not run because the default interpreter lacks core dependencies.

Companion files:

- `FILE_INVENTORY.tsv`: every original file, its byte size and category, including installed dependencies.
- `FILE_GUIDE.md`: one entry for each of the 266 project files, with its purpose or inspection result.
- `REVIEW_DETAILS.json`: source definitions, dataset dimensions, document counts, database schemas/counts, duplicate fingerprints and inspection coverage.
- `FOCUSED_CHECKS.json`: results of targeted local reproductions of correctness defects.

## What the application does

1. Accepts CSV or Excel uploads, or generates a 600-row retail, SaaS or supply-chain example.
2. Computes a fast profile: column types, missing values, duplicates, distributions, correlations, outliers and a heuristic health score.
3. Runs an analytical pipeline that plans the analysis, classifies columns, computes KPIs, examines segments, performs statistical tests, analyzes dates and produces charts and narratives.
4. Generates Markdown, PDF and PowerPoint reports.
5. Separately trains classification or regression models, ranks them, computes feature importance and saves a prediction bundle.
6. Answers conversational questions by asking an LLM for Python calculations and then asking it to explain the output.

The analytical pipeline and AutoML are separate execution paths. The current AutoML code supports classification and regression. The older PCA/unsupervised artifacts do not correspond to a current unsupervised implementation in `automl_engine.py`.

## Folder responsibilities

| Folder or file | Responsibility |
|---|---|
| `backend/main.py` | FastAPI application, 18 routes, upload/session handling, profiling, analysis, chat, cleaning, training, prediction and experiment retrieval |
| `backend/config.py` | Loads `.env`, defines model/provider settings, storage paths and application defaults |
| `backend/graph/` | Shared typed state, a compiled sequential LangGraph, and the separate concurrent executor actually called by the app |
| `backend/agents/` | Eleven pipeline modules: loading, supervision, schema, quality, KPI, EDA, diagnosis, hypothesis, trend, visualization and reporting |
| `backend/services/` | Profiling, cleaning, model training/XAI, LLM requests, key pools, jobs, persistence, storage and JSON serialization |
| `backend/tools/` | Statistical functions, Plotly charts, benchmark rules, dataset comparison, report slides, Python/SQLite tools and an unused cache layer |
| `frontend_web/` | React 19/Vite application, eight pages, shared UI components, source assets, npm lockfile, installed dependencies and compiled build |
| `frontend/` | Streamlit home page and seven analysis pages; much of this interface calls backend Python modules directly |
| `test/` | Five principal CSV fixtures |
| `data/` | Clean/noisy retail fixtures and a relational SQLite demo |
| `artifacts/` | Stored dataset copies, historical model pickles, current joblib model bundles and text report copies |
| `reports/`, `backend/reports/` | Historical PDF, PowerPoint and text outputs |
| `ds_agent.db` | Local projects, leaderboards, reports, chat records and experiment history |
| `.cache/analysis/` | One persisted analysis-cache object; cache helpers are not wired into the main pipeline |
| `catboost_info/` | Training logs, TensorBoard event data and a temporary CatBoost file |
| `uploads/`, `charts/` | Present but empty at inventory time |
| `README.md` | Most current description and startup commands, with several overstatements relative to the implementation |
| `COMPLETE_NEW_README.md` | Older architecture/hosting proposal, including services not used by the current code |
| `Autonomous_Data_Science_Agent_Roadmap.md` | Original plan and proposed architecture rather than a reliable completion checklist |

## Execution architecture

The React path is: upload/profile request → process-local session dictionary → start background job → poll status/result → display analysis or AutoML output. The React state itself lives in a Context/reducer, not durable browser storage. The Streamlit path mostly runs the Python analysis directly using Streamlit session state.

The active analytical executor uses these stages:

1. Dataset loader, then supervisor.
2. Schema and quality concurrently.
3. KPI and EDA concurrently.
4. Diagnostic agent.
5. Hypothesis, trend and visualization concurrently.
6. Report agent.

`create_analyst_graph()` also builds a sequential LangGraph, but `run_analyst_pipeline()` does not invoke that compiled graph. Documentation should describe this distinction.

The LLM layer uses HTTP requests to Groq and NVIDIA NIM, with model tiers, retries and key rotation. Configuration supports 11 Groq keys and 7 NVIDIA keys. Configured key counts are not proof of validity or availability. R2 and Supabase integrations fall back to local files and SQLite; the background synchronization threads are not durable jobs.

## Findings requiring attention

### 1. Generated Python executes with full server privileges — critical

`backend/tools/python_tool.py:37` calls `exec` with unrestricted built-ins. The API chat route passes LLM-generated code to it. This is not a sandbox despite its name and documentation. Generated code can import modules and access the process's files, environment and network. There are no execution time or memory limits, and stdout redirection is process-wide.

The API has no implemented authentication or project ownership checks. JWT settings exist only as configuration. CORS permits every origin. Before exposing the service, generated code must execute in an isolated worker with constrained inputs, resources and permissions, and API access must be tied to authenticated project ownership.

### 2. Database project identities are inconsistent — high, confirmed in stored data

`csv_loader.py:79` calls `save_project()` without preserving the active project ID. `supabase_service.py:85` generates a new UUID. Reports and chat use the original session ID.

The current SQLite database contains 78 projects, 25 leaderboard rows, 55 reports, 25 chat messages and 2 experiments. A read-only join found **all 55 reports and all 25 chat messages have no matching project**. The PostgreSQL schema declares foreign keys, so these writes can fail remotely and fall back locally. Project creation and every subsequent write must share one identifier.

### 3. Concurrent stages violate data dependencies — high, reproduced with stub agents

Quality consumes `schema_metadata` and the converted dataframe, but runs beside schema before its result is merged (`workflow.py:97`). Consequently ID collision, date and recommended-measure checks lack their schema context on a fresh run.

Visualization consumes `trend_results`, but runs beside trend. The newly computed trend cannot be used to produce its richer trend/MoM/seasonality charts during that run. Parallel branch merges also omit several returned `errors` lists. A focused execution of the actual orchestration function with stub nodes confirmed missing schema input, missing trend input, and loss of a quality error.

### 4. Optuna results do not update the trained model — high

`automl_engine.py:463` obtains best parameters and stores them in a report. It never applies those parameters, refits the winner or recomputes scores before saving it. The UI can claim tuning succeeded while predictions still use the untuned estimator. Tuning supports only selected tree families, although it is attempted for other winners too.

### 5. Model evaluation is optimistic and inconsistent — high

The preprocessor is fitted once before cross-validation; CV is run on those already-transformed training values (`automl_engine.py:399`). Fold validation data has therefore influenced preprocessing. Put preprocessing inside each CV pipeline.

The leaderboard chooses the winner using the held-out test score (`automl_engine.py:455`), so that same test set participates in model selection. An independent final evaluation set is needed. Classification CV uses macro F1, while the primary leaderboard score uses weighted F1 and the UI labels it macro F1. These are different metrics.

Automatic cleaning can also impute/clip the target and learn transformation statistics from the entire dataset before splitting if `/api/clean` precedes AutoML. Target handling and feature preprocessing need separate policies.

### 6. Reports and several insights do not reach the React UI correctly — high

`report_agent.py:238` initializes `report_url` to an empty string and never changes it. The background upload URL is saved only in its worker, while the response returns the empty string. The React download button depends on that URL, and the API has no report-download route.

Both analysis response builders omit trend results, benchmark results and the PowerPoint path; the background response also omits the analysis plan. `InsightsPage.jsx` reads `kpi_narrative`/`summary`, `trend_results.narrative`, `hypothesis_results.narrative` and `tests`, while the agents produce `kpi_interpretation`, `trend_narrative`, `executive_summary` and `tests_conducted`. The UI can show unavailable messages despite computed results.

### 7. Reproducible installation is incomplete — high

`requirements.txt` omits the directly required `scikit-learn` and `joblib`, as well as feature packages such as `python-pptx`, XGBoost, LightGBM, CatBoost, Optuna and SHAP. The last group has fallback behavior, but their advertised features will be absent without installation. `.xls` support also needs an appropriate reader; `openpyxl` alone is for the newer workbook format. TestClient-based tests need a declared test dependency set.

The default Python 3.13.5 interpreter here cannot import NumPy, and FastAPI and LangGraph are also unavailable. No project virtual environment was found. This prevents an end-to-end runtime verdict. `.env.example` is stale: it lacks the current Groq pool and uses an older NVIDIA model setting.

### 8. Pareto's 80% cutoff is wrong — high, reproduced

`stats_tools.py:533` counts only categories whose cumulative share is at or below 80%, excluding the category that crosses the threshold. With shares of 70%, 20%, 10%, it reports one category drives 80%; two are required. This affects diagnostic summaries and charts.

### 9. Benchmark matching can compare incompatible units — high, reproduced

`benchmarks.py` matches any token from a benchmark name and uses a KPI mean or total without checking units or time period. A raw `profit` amount of 35 is matched to **Profit Margin %** and rated **World Class**. The report passes core KPIs rather than incorporating the separately computed domain-specific ratios.

The thresholds and percentile labels are hardcoded, with source names but no links, derivation or validation records in the code. They should be treated as configurable example rules until verified, not measured industry percentiles.

### 10. Cleaning can create duplicate columns — medium, reproduced

`clean_column_names()` turns both `A-B` and `A B` into `a_b`, without uniqueness handling. Later column access can return a dataframe instead of a series and fail. Cleaning always trims strings and drops empty columns, even when the four public switches are false. The analysis/chat/profile routes continue using the original session dataframe; only AutoML explicitly prefers `df_cleaned`.

### 11. Several frontend paths are incomplete — medium

- Sample loading creates only an overview object, never calls the existing profile-by-project endpoint and omits column names, so profiling-dependent views and the AutoML target selector are incomplete for samples.
- AutoML uses hardcoded relative `/api` requests rather than the configured API client, so a separate API origin can work for other pages and fail for training/prediction.
- `SET_PROJECT` retains the previous analysis, so uploading another dataset can display stale findings until a new analysis completes.
- Chat messages and AutoML results live in page-local state and are lost when those pages unmount. The API chat route saves messages but does not read history into later prompts.
- EDA builds box plots from five percentile values as if they were raw observations and drops zero values with `filter(Boolean)`, yielding misleading quartiles.
- React has no controls wired to the cleaning or experiment-history endpoints, and no counterpart to Streamlit's dataset comparison page.

### 12. Streamlit has separate integration defects — medium

The successful sample-load path builds its analysis dataframe from the API's ten-row preview, although the sample has 600 rows. The dataset comparison page looks for `dataset_data` in session state while upload stores `df`. Uploaded project IDs are based on a six-character filename prefix, and report filenames truncate IDs to eight characters, creating collision opportunities across runs with matching names/prefixes.

### 13. Jobs and sessions do not provide durable operation — medium

Sessions and jobs are dictionaries within one Python process. Restart loses them; multiple API worker processes do not share them. Sessions have no eviction or size limit. Every submitted job gets a thread, although a semaphore limits running jobs to three. Queue length is unbounded.

Progress callbacks are not connected by the API, so normal progress jumps from 5% to 100% rather than showing real stages. There is no cancellation or hard execution deadline. Uploads are read wholly into memory without an enforced size limit.

### 14. Key monitoring describes an unused pool — medium

`main.py` exposes newly constructed `QuotaAwareKeyPool` objects, while `llm_service.py` makes requests using separate `KeyPool` instances. Health counters therefore do not reflect actual traffic. Both implementations can choose a still-cooling key when all keys are exhausted. LLM exhaustion is returned as a normal text string, which narrative agents can incorporate into reports instead of treating it as a failed dependency.

### 15. Dataset fingerprints miss real changes — medium, reproduced

Experiment hashes use the dataframe shape and first five rows. Cache fingerprints use the structure and first/last ten rows. Changing row 50 in a 100-row dataset leaves both fingerprints unchanged. This defeats full-data version tracking and would create stale cache hits if the cache were integrated. Cache helpers currently have no call sites in the application outside their module.

### 16. Additional analytical limitations

- Statistical prompts contain an incorrect example interpreting a p-value as the probability that a difference is due to chance. The generated wording can mislead decision makers.
- The third hypothesis-test path selects a t-test when its selector returns ANOVA, effectively examining only the top two groups.
- The comparator marks a metric significant if either of two tests passes, without adjusting for running both or testing multiple metrics. It can also ignore a requested numeric segment such as `bedrooms` because candidate segments are restricted to object/category types.
- Combined outlier detection uses the smaller of two counts as their claimed agreement, without computing the intersection of flagged rows.
- Time-series helpers do not consistently represent missing calendar months; the manual Mann–Kendall calculation omits tie correction. Seasonality heuristics can label variation within a single year as a recurring pattern.
- Negative profit is treated as a quality violation even though losses may be valid observations. The fast profiler and pipeline quality agent use different health formulas, so their scores are not interchangeable.
- Numeric IDs can enter AutoML features; an invalid requested target silently falls back to a guessed target. Regression parsing strips characters and can corrupt scientific-notation values. If every estimator fails, saving attempts to call `.lower()` on a missing best model name.
- Feature-importance percentages are normalized over the displayed top features and do not establish literal percentages of model decisions or causal impact.

### 17. Maintenance and deployment gaps

No root `.gitignore`, CI workflow, Docker configuration, Python lockfile or dedicated automated frontend test suite was found. `.env` holds nonempty credential settings, so a root ignore policy is particularly important before sharing or committing the folder. Credential validity or exposure was not tested.

The frontend contains unused Vite/TypeScript starter files. Production compilation succeeds, but Plotly produces a roughly 4.68 MB minified chunk and Three.js another 0.91 MB chunk. Eight pages are imported eagerly. There are 32 byte-identical file groups, mostly repeated datasets/models/report copies, worth documenting before deciding which outputs to retain.

Documentation describes sandboxing, nine-slide decks, SQL chat, completed tuning, a LangGraph execution path and production readiness more strongly than the implementation supports. The SQL helper uses in-memory SQLite and is imported but not called by API chat. The relational demo database is not connected to an application database-ingestion path. Generated decks in this folder contain seven or eight slides.

## Data and historical outputs

| Fixture | Rows | Columns | Missing cells | Duplicate rows |
|---|---:|---:|---:|---:|
| `test/customers-1000.csv` | 1,000 | 12 | 0 | 0 |
| `test/dataset.csv` | 500 | 6 | 5 | 0 |
| `test/kc_house_data.csv` | 21,613 | 21 | 0 | 0 |
| `test/noisy_regression_2000x13.csv` | 2,000 | 13 | 60 | 0 |
| `test/tested.csv` | 418 | 12 | 414 | 0 |
| `data/test_clean_sales.csv` | 600 | 11 | 0 | 0 |
| `data/test_noisy_sales.csv` | 605 | 10 | 185 | 5 |

The customer fixture includes contact-information fields. Row values were not copied into the review. The enterprise demo database contains 120 customers, 30 products and 1,500 orders. Artifact CSVs cover repeated Iris, housing, Titanic and retail examples; their individual dimensions are in the file guide and JSON details.

All 24 PDFs were readable for text extraction: 10 have two pages and 14 have three. All 24 PowerPoint packages were readable: 20 have seven slides and 4 have eight. Their extracted text did not contain the application's literal “Unable to contact LLM” failure marker. This limited check is not validation of the narratives, chart accuracy or document layout.

Model files comprise 15 historical `.pkl` models and 26 newer `.joblib` bundles; the sixteenth pickle is a tiny analysis cache file. They were fingerprinted without loading executable serialization formats. The folder mixes outputs from older and newer implementations.

## Validation performed

| Check | Result |
|---|---|
| Full file inventory | Completed: 20,603 original files |
| Python AST parsing | All 56 Python files parsed successfully |
| React/Vite production build | Passed, 2,862 modules transformed, approximately 6.8 seconds; large-chunk warnings |
| CSV structure/content profiling | All 26 read; row/column/null/duplicate counts recorded |
| SQLite inspection | Both opened read-only; table structure/counts inspected; orphan links counted |
| PDF/PPTX extraction | All 48 document packages readable for structural/text inspection |
| Isolated function checks | Reproduced Pareto cutoff, fingerprint collisions, duplicate cleaned names and benchmark unit mismatch |
| Orchestration with stub nodes | Reproduced missing dependency inputs and discarded branch errors |
| Full API, LLM and AutoML tests | Not run; current default Python environment lacks core dependencies |

The repository contains eight `test_*.py` scripts plus `verify_servers.py`. Several scripts run work at import time, call real LLM/cloud services or write artifacts. Some print success without substantive assertions; the master suite is stronger but checks mainly successful execution and artifact existence. They do not provide reliable coverage for the defects above, and running all files through pytest would not be equivalent to a clean, isolated test suite.

## Suggested order of work

1. Isolate generated code execution and implement authentication/project ownership before exposing the server.
2. Make Python installation reproducible and align `.env.example` with current settings.
3. Repair project IDs, dependency ordering, branch error propagation and API response contracts.
4. Correct Pareto/benchmark behavior and AutoML evaluation; apply and refit tuned parameters.
5. Repair report downloads, sample profiling, stale UI state and Streamlit sample handling.
6. Add targeted regression tests for these concrete failures, then run the full application with cloud services explicitly configured or mocked.
7. Add persistent session/job management, deployment configuration and cleanup/retention rules; update documentation to match verified behavior.

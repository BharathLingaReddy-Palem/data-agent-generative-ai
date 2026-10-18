> **Historical proposal — not the current feature/setup reference.** Use [README.md](README.md) and [FIXES.md](FIXES.md) for implemented behavior and verification. The plans below include unimplemented features and old provider/model/pricing/credit assumptions that have not been verified. They are preserved as planning history, not current deployment instructions or guarantees.

# 🤖 Autonomous Data Science Agent — Next-Gen Architecture & Free-Tier Guide

> **Project Feasibility:** 100% Feasible, Production-Grade, and completely achievable with **$0 cost** and **Zero Credit Card / Registration Headaches**.

---

## 📌 Table of Contents
1. [Feasibility Assessment: Is This Project Possible?](#1-feasibility-assessment-is-this-project-possible)
2. [Why You Faced Oracle Cloud Issues & Why We Are Dropping It](#2-why-you-faced-oracle-cloud-issues--why-we-are-dropping-it)
3. [How to Leverage Your Lightning AI Credits ($96.87)](#3-how-to-leverage-your-lightning-ai-credits-9687)
4. [Best 100% Free-of-Cost Tools & Services across the Web](#4-best-100-free-of-cost-tools--services-across-the-web)
5. [Top 3 Production Architectures (Choose Your Best Fit)](#5-top-3-production-architectures-choose-your-best-fit)
6. [Multi-Agent LangGraph Pipeline Deep Dive](#6-multi-agent-langgraph-pipeline-deep-dive)
7. [Step-by-Step Implementation & Execution Roadmap](#7-step-by-step-implementation--execution-roadmap)
8. [Complete Environment Variables Reference](#8-complete-environment-variables-reference)

---

## 1. Feasibility Assessment: Is This Project Possible?

### **Verdict: 100% YES.**
Building an **Autonomous Data Science Agent** that ingests raw CSVs, cleans data, performs exploratory data analysis (EDA), trains multiple machine learning models, ranks them on an AutoML leaderboard, chats with dataset insights, and outputs a publication-ready PDF report is **fully achievable, robust, and highly valued in the industry**.

### Why it works seamlessly today:
* **LangGraph** provides deterministic graph orchestration and cyclical agent workflows with typed state management (`AgentState`).
* **Ultra-Fast Free LLMs** (Groq LLaMA 3.3 70B and Google Gemini 2.0 Flash) provide sub-second reasoning for data summarization, anomaly explanation, and chart recommendations without paying a single dollar.
* **Classical ML Libraries** (Scikit-Learn, XGBoost, LightGBM, CatBoost) are lightweight, fast, and train tabular datasets in seconds to minutes on modest CPU/GPU resources.
* **ReportLab + Plotly** allow programmatic generation of interactive charts and PDF exports without complex rendering engines.

---

## 2. Why You Faced Oracle Cloud Issues & Why We Are Dropping It

Many developers encounter major issues with Oracle Cloud Free Tier:
1. **Strict Payment Verification:** Rejects valid international debit/credit cards due to strict 3D Secure / address verification algorithms.
2. **"Out of Capacity" Errors:** The famous 4-core ARM free instances (Ampere A1) are frequently out of stock in many global data regions.
3. **Complex Networking:** Setting up Virtual Cloud Networks (VCN), security lists, iptables, and floating IPs creates unnecessary friction for AI application deployment.

**The Solution:** We replace Oracle VM with **Lightning AI Studio** (using your existing credits) OR **Hugging Face Spaces + Streamlit Community Cloud** (100% free forever, 1-click deploy from GitHub, zero credit card required).

---

## 3. How to Leverage Your Lightning AI Credits ($96.87)

Your Lightning AI account currently has **$96.87 credits**. Lightning AI is an exceptional platform for this project!

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LIGHTNING AI STUDIO                             │
│                                                                        │
│  ┌───────────────────────────┐         ┌────────────────────────────┐  │
│  │   Streamlit Web UI        │ ◄─────► │   FastAPI + LangGraph      │  │
│  │   (Port 8501 / Plugin)    │  HTTP   │   (Port 8000 / Plugin)     │  │
│  └─────────────┬─────────────┘         └─────────────┬──────────────┘  │
│                │                                     │                 │
│                ▼                                     ▼                 │
│    Public URL: https://...               AutoML Engine (XGB/LGBM)     │
│    (Shareable Demo Link)                 + Persistent NVMe Storage     │
└────────────────────────────────────────────────────────────────────────┘
```

### Why Lightning AI is Great for This Project:
1. **Zero Setup Hassle:** Provides a full Ubuntu Linux environment with Python, GPU/CPU, VS Code browser editor, and terminal out of the box.
2. **Built-in Streamlit & Port Plugins:**
   * **Streamlit Plugin:** One-click launch with an instant **Public Shareable Link** (`https://...lightning.ai`).
   * **Port Plugin:** Easily expose port `8000` (FastAPI) or port `8501` (Streamlit) to the internet with automatic HTTPS.
3. **Huge Compute Power for AutoML:**
   * You can use 4-CPU / 8-CPU instances (or switch to a T4 GPU for large datasets/deep learning) for fast parallel cross-validation and hyperparameter tuning.
4. **Auto-Sleep / Smart Cost Savings:**
   * When you are not using the studio, it pauses automatically. Your $96.87 credits can easily last for months of development and testing!
5. **Pipelines & Inference (`My Pipelines` tab):**
   * You can automate multi-step data science pipelines and deploy endpoints directly using Lightning AI's native orchestration if desired.

---

## 4. Best 100% Free-of-Cost Tools & Services across the Web

Here is the curated matrix of free, reliable, no-hassle tools suitable for your agent:

| Category | Tool / Platform | Free Tier Offering | Why It Is Perfect |
|---|---|---|---|
| **Cloud Studio / Compute** | **Lightning AI** | $96.87 credits + Free quota | Unified FastAPI + Streamlit hosting, public URLs, high CPU/GPU power. |
| **Frontend Hosting** | **Streamlit Community Cloud** | Free forever, unlimited public apps | Deploys directly from your GitHub repository with auto-reloads on git push. |
| **Backend / Docker Hosting** | **Hugging Face Spaces** | Free 2 vCPU + 16 GB RAM Space | Runs FastAPI inside Docker on port 7860; never sleeps or wakes up automatically. |
| **Alternative Backend** | **Render / Koyeb** | Free tier web services | Free REST API hosting for FastAPI. |
| **Primary LLM** | **Groq Cloud** | Free LLaMA 3.3 70B & LLaMA 3.1 8B (30 RPM, 1000 req/day) | Ultra-fast token generation (~300 tokens/sec) for instant agent summaries. |
| **Alternative LLM** | **Google AI Studio** | Free Gemini 2.0 Flash / Gemini 1.5 Flash (15 RPM) | Free API key, 1M+ token context window, incredible reasoning. |
| **Database** | **Turso (libSQL)** | 500 databases, 5 GB storage, 1B row reads/mo | SQLite at the edge, ultra-lightweight, zero server maintenance. |
| **Alternative DB** | **Supabase** | Free PostgreSQL (500 MB DB + 1 GB Storage + Auth) | Full relational Postgres with built-in storage and authentication. |
| **File / Model Storage** | **Cloudinary** | 25 GB monthly storage & bandwidth | Stores uploaded CSVs, `.pkl` model checkpoints, and PDF reports with CDN links. |
| **Reporting** | **ReportLab** | 100% Free Open-Source Python Library | Programmatic PDF creation with custom styling, tables, and embedded figures. |

---

## 5. Top 3 Production Architectures (Choose Your Best Fit)

### 🥇 Architecture Option 1: The Lightning AI Studio Powerhouse (Recommended)
* **Frontend:** Streamlit running inside Lightning Studio (exposed via Streamlit plugin public URL).
* **Backend:** FastAPI + LangGraph running inside the same studio (internal communication `http://localhost:8000` or public port).
* **LLM:** Groq (LLaMA 3.3 70B) or Google Gemini 2.0 Flash (free API keys).
* **Database:** Turso (libSQL) or local SQLite in Studio's persistent disk `/workspace`.
* **Storage:** Local Studio storage `/workspace/artifacts` + optional Cloudinary sync.
* **Benefits:** Simplest setup, zero deployment friction, high CPU RAM for AutoML, and leverages your $96.87 credits.

---

### 🥈 Architecture Option 2: Pure Serverless & Zero Credit Card (Streamlit Cloud + HF Spaces)
* **Frontend:** Streamlit Community Cloud (hosted free on `https://your-app.streamlit.app`).
* **Backend:** FastAPI hosted on Hugging Face Spaces (Docker, 16 GB RAM free on `https://username-space.hf.space`).
* **LLM:** Groq Cloud with key rotation.
* **Database:** Turso Cloud.
* **Storage:** Cloudinary (CSVs, `.pkl` models, PDFs).
* **Benefits:** 100% independent cloud deployment, no credit cards required anywhere, never expires.

---

### 🥉 Architecture Option 3: Hybrid Pro (Streamlit Cloud + Lightning AI Worker)
* **Frontend:** Streamlit Cloud for 24/7 public portfolio presentation.
* **Backend API & ML Training:** Lightning AI Studio running FastAPI to handle heavy computations, training, and report compilation.

---

## 6. Multi-Agent LangGraph Pipeline Deep Dive

The multi-agent workflow is modeled as a state machine where each agent node executes specialized transformations on `AgentState`:

```
                    ┌─────────────────────────┐
                    │      Upload CSV         │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   1. Data Cleaner Node  │
                    │   (Imputation, Types)   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     2. EDA Agent        │
                    │   (Stats & LLM Insights)│
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ 3. Visualization Agent  │
                    │  (Plotly Chart Configs) │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  4. Task Detector Node  │
                    │ (Classification/Regress)│
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  5. Model Trainer Agent │
                    │ (XGB, LGBM, RF, CatB)   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ 6. Evaluator Leaderboard│
                    │  (Metrics & Pickling)   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   7. Report Agent       │
                    │ (PDF via ReportLab)     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   Interactive Chat Q&A  │
                    │ (Query over dataset)    │
                    └─────────────────────────┘
```

### Agent Roles & Deliverables:
1. **CSV Loader Node:** Reads CSV bytes from upload / Cloudinary and instantiates a Pandas DataFrame.
2. **Data Cleaner Node:** Detects missing value ratios, imputes numeric/categorical features, strips whitespace, and removes duplicate rows.
3. **EDA Agent Node:** Computes descriptive statistics, correlation matrices, skewness, and uses LLM for business-level textual insights.
4. **Visualization Agent Node:** Emits Plotly JSON specifications for distributions, correlations, box plots, and scatter relationships.
5. **Task Detector Node:** Inspects target column cardinality and data type to classify task as Binary Classification, Multi-class Classification, or Regression.
6. **Model Trainer Node (AutoML):** Trains XGBoost, LightGBM, CatBoost, and Random Forest using K-Fold cross-validation.
7. **Evaluator Node:** Calculates Accuracy, F1, ROC-AUC, RMSE, MAE, R2 scores, picks the winner, and serializes `.pkl` artifacts.
8. **Report Agent Node:** Compiles an executive PDF document containing structured headings, summary tables, metrics, and chart snapshots.

---

## 7. Step-by-Step Implementation & Execution Roadmap

### Phase 1: Environment & Project Setup
* Create project directory structure:
  ```
  autonomous-ds-agent/
  ├── backend/
  │   ├── agents/
  │   ├── graph/
  │   ├── services/
  │   ├── api/
  │   └── main.py
  ├── frontend/
  │   ├── pages/
  │   └── app.py
  └── requirements.txt
  ```
* Install dependencies (`fastapi`, `uvicorn`, `langgraph`, `langchain-groq`, `pandas`, `scikit-learn`, `xgboost`, `lightgbm`, `catboost`, `plotly`, `reportlab`, `cloudinary`, `libsql-client`).

### Phase 2: Core Data Agents & Graph Wiring
* Implement `data_cleaner.py` and `eda_agent.py`.
* Implement `visualization_agent.py` producing interactive Plotly chart specs.
* Define `AgentState` in LangGraph and compile the base data exploration graph.

### Phase 3: AutoML Engine & Chat System
* Implement task detection logic (classification vs. regression).
* Build multi-model training and evaluation harness.
* Integrate dataset conversational Q&A endpoint using Groq LLaMA 3.3 70B / Gemini 2.0 Flash.

### Phase 4: PDF Generation & UI Assembly
* Build `report_agent.py` using `ReportLab`.
* Construct Streamlit multi-page interface:
  * `01_upload.py`: Dataset upload & preview table.
  * `02_eda.py`: Statistical summary & interactive Plotly charts.
  * `03_models.py`: AutoML Leaderboard & model metrics.
  * `04_chat.py`: Real-time Q&A with dataset insights.
  * `05_reports.py`: 1-Click PDF Report Download.

### Phase 5: Deployment
* **Option A (Lightning AI):** Run inside Lightning Studio with Streamlit & Port plugins.
* **Option B (Free Cloud):** Push to GitHub -> Deploy Backend to Hugging Face Spaces / Render -> Deploy Frontend to Streamlit Community Cloud.

---

## 8. Complete Environment Variables Reference

Create a `.env` file in `backend/`:

```bash
# 🤖 LLM (Groq Cloud - Free at console.groq.com)
GROQ_API_KEY=gsk_your_groq_api_key_here

# 🤖 Alternative LLM (Google AI Studio - Free at aistudio.google.com)
GEMINI_API_KEY=your_gemini_api_key_here

# 🗄️ Database (Turso - Free at turso.tech)
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your_turso_token_here

# ☁️ Storage (Cloudinary - Free at cloudinary.com)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# 🔐 Security
JWT_SECRET_KEY=generate_with_python_secrets_token_hex_32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

# 🌐 App Config
PORT=8000
ALLOWED_ORIGINS=*
```

---

## 💡 Summary & Recommendation

1. **Yes, this project is 100% possible and practical.**
2. **You do NOT need Oracle Cloud.** Your **Lightning AI credits ($96.87)** give you a far better, more powerful, and headache-free developer environment with built-in public URLs for Streamlit and FastAPI.
3. **If you want a 100% free permanent deployment**, you can also use **Streamlit Community Cloud + Hugging Face Spaces / Render + Groq / Gemini**, which costs $0 forever without asking for a credit card.

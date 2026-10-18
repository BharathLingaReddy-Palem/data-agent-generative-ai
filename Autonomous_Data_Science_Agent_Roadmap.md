> **Historical proposal — not the current feature/setup reference.** Use [README.md](README.md) and [FIXES.md](FIXES.md) for implemented behavior and verification. The plans below include unimplemented features and old provider/model/pricing/credit assumptions that have not been verified. They are preserved as planning history, not current deployment instructions or guarantees.

# Autonomous Data Science Agent - Complete Project Roadmap

## 1. Tech Stack

### Frontend
- Streamlit (Recommended)
- Gradio (Alternative)
- Next.js (Advanced)

### Backend
- FastAPI
- LangGraph
- Pandas
- NumPy
- Scikit-learn

Install:
```bash
pip install fastapi langgraph pandas numpy scikit-learn uvicorn
```

---

## 2. Agents Required

### Agent 1: CSV Upload Agent
Input:
- sales.csv
- student.csv
- heart.csv

Output:
- Pandas DataFrame

### Agent 2: Data Cleaning Agent
Tasks:
- Handle missing values
- Remove duplicates
- Fix data types
- Detect outliers

Libraries:
- pandas
- numpy

### Agent 3: EDA Agent
Generate:
- Rows and columns count
- Statistics
- Correlations
- Target distribution

### Agent 4: Visualization Agent
Create:
- Histogram
- Boxplot
- Heatmap
- Scatterplot

Libraries:
- matplotlib
- seaborn
- plotly

### Agent 5: Model Selection Agent
Detect:
- Classification
- Regression
- Clustering

Choose:
- Random Forest
- XGBoost
- LightGBM
- CatBoost

### Agent 6: Training Agent
Perform:
- Cross Validation
- Hyperparameter Search

### Agent 7: Report Agent
Generate:
- Executive Summary
- Best Features
- Model Performance
- Recommendations

Output:
- PDF
- Markdown

---

## 3. Database

### Option A (Recommended)
Turso

Store:
- Users
- Projects
- Reports
- Chat History

### Option B
Neon PostgreSQL

Better for production-level architecture.

---

## 4. LLM

### Primary
OpenRouter

Models:
- Qwen
- Llama
- DeepSeek

### Alternative
Google AI Studio

Model:
- Gemini 2.5 Flash

---

## 5. Charts

Use Plotly because:
- Interactive
- Browser-friendly
- Easy export

---

## 6. PDF Generation

Library:
```bash
pip install reportlab
```

Include:
- Executive Summary
- EDA Results
- Charts
- Metrics

---

## 7. File Storage

### MVP
Store files locally:
```text
uploads/
```

### Future
Use:
- Cloudinary
- S3-compatible storage

---

## 8. Free Hosting (24/7)

### Frontend
- Streamlit Community Cloud

### Backend
- Koyeb
- Render (free tier sleeps)

### Database
- Turso
- Neon

---

## 9. LangGraph Workflow

```text
Upload CSV
      ↓
Data Cleaner Agent
      ↓
EDA Agent
      ↓
Visualization Agent
      ↓
Task Detection Agent
      ↓
Model Selection Agent
      ↓
Training Agent
      ↓
Evaluation Agent
      ↓
Report Agent
      ↓
PDF Download
```

---

## 10. Resume Booster Features

### Feature 1: Natural Language Queries
Example:
- Show top 10 correlated features

### Feature 2: Dataset Chat
Example:
- What affects student marks most?

### Feature 3: AutoML Leaderboard
Example:
- XGBoost 94.2%
- Random Forest 92.8%
- CatBoost 95.0%

### Feature 4: RAG Over Reports
Example:
- What were the key insights?

### Feature 5: Multi-user Login
Using:
- JWT
- FastAPI
- Turso / Neon

---

# Development Timeline

## Week 1
- CSV Upload
- Data Cleaning
- EDA

## Week 2
- Visualizations
- LangGraph Workflow

## Week 3
- AutoML
- Model Training

## Week 4
- PDF Reports
- Deployment

---

# Final Goal

Build a production-ready Autonomous Data Science Agent that:
1. Accepts CSV datasets.
2. Cleans and analyzes data automatically.
3. Creates visualizations.
4. Selects the best ML model.
5. Trains and evaluates models.
6. Generates downloadable reports.
7. Supports multiple users.
8. Runs as a deployed AI agent application.



# Autonomous Data Science Agent using LangGraph

## Project Overview

Build a production-grade Autonomous Data Science Agent that can automatically:

- Upload CSV datasets
- Clean data
- Perform EDA (Exploratory Data Analysis)
- Engineer features
- Select ML models
- Train models
- Evaluate performance
- Generate visualizations
- Create professional reports

This project demonstrates:

- LangGraph
- Multi-Agent Systems
- AutoML
- Data Engineering
- Explainable AI
- Workflow Orchestration
- Production AI Architecture

---

# System Architecture

```text
User Uploads CSV
        │
        ▼
 Supervisor Agent
        │
 ┌──────┼─────────┬──────────┬─────────┐
 ▼      ▼         ▼          ▼         ▼
Schema  Cleaner   EDA     Feature    Model
Agent   Agent    Agent   Engineer   Selector
                                    Agent
        │
        ▼
 Training Agent
        │
        ▼
 Evaluation Agent
        │
        ▼
 Visualization Agent
        │
        ▼
 Report Agent
```

---

# LangGraph State

```python
from typing import TypedDict

class DSState(TypedDict):
    file_path: str
    dataset_info: dict
    cleaned_data_path: str
    eda_results: dict
    features: list
    target_column: str
    model_name: str
    metrics: dict
    charts: list
    report_path: str
```
...

(Full project specification from the previous response, including all agents, workflow, tech stack, folder structure, and resume impact sections.)


autonomous-data-science-agent/

├── app/
│   ├── agents/
│   │   ├── supervisor.py
│   │   ├── schema_agent.py
│   │   ├── cleaner_agent.py
│   │   ├── eda_agent.py
│   │   ├── feature_agent.py
│   │   ├── model_agent.py
│   │   ├── training_agent.py
│   │   ├── evaluation_agent.py
│   │   ├── visualization_agent.py
│   │   ├── explainability_agent.py
│   │   └── report_agent.py
│   │
│   ├── graph/
│   │   ├── workflow.py
│   │   └── state.py
│   │
│   ├── tools/
│   ├── database/
│   ├── reports/
│   ├── charts/
│   └── api/
│
├── frontend/
│   └── streamlit_app.py
│
├── requirements.txt
├── README.md
└── docker-compose.yml



Recommended Tech Stack
Workflow
LangGraph
LLM
Qwen 3
Llama 3.3
Gemini
Data Processing
Pandas
Polars
Machine Learning
Scikit-Learn
AutoML
AutoGluon
FLAML
Optuna
Explainability
SHAP
LIME
Visualization
Plotly
Matplotlib
Database
PostgreSQL
Vector Database (Optional)
ChromaDB
Qdrant
Backend
FastAPI
Frontend
Streamlit
Monitoring
LangSmith
Deployment
Railway
Render
Hugging Face Spaces












                          ┌────────────────────────┐
                          │ Uploaded CSV / Excel   │
                          └───────────┬────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │         🤖 Senior AI Model Architect             │
             │   (Inspects row count, features, sparsity, task) │
             └────────────────────────┬─────────────────────────┘
                                      │
               ┌──────────────────────┴───────────────────────┐
               ▼                                              ▼
    [ Supervised Dataset ]                         [ Unsupervised Dataset ]
    • Explains why dataset is Supervised           • Explains why dataset is Unsupervised
    • Recommends TOP 2-3 optimal models            • Recommends TOP 1-2 optimal algorithms
      (e.g., LightGBM + XGBoost)                     (e.g., K-Means + PCA)
    • Explains WHY other models were filtered out  • Explains WHY (e.g., density vs clustering)
               │                                              │
               └──────────────────────┬───────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │       ⚡ Selective Training (Top 2-3 Only)       │
             │  • Saves 70% CPU/RAM compute time                │
             │  • Zero memory bottlenecks                       │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │     🏆 Single Winning Model Storage in R2        │
             │  • Only the #1 Champion `.pkl` is saved to R2    │
             │  • Zero storage waste!                           │
             └──────────────────────────────────────────────────┘

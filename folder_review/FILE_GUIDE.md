> **Historical snapshot from 8 October 2026.** Inventory counts and findings describe the original review, before subsequent fixes. For current behavior, regression checks and resolved issues, see [README.md](../README.md) and [FIXES.md](../FIXES.md).

# Complete project-file guide

All 266 original project files outside installed dependencies and Python bytecode caches. For every one of the 20,603 original paths, see FILE_INVENTORY.tsv. Sizes are bytes. Detailed source findings are in PROJECT_REVIEW.md.

## .cache

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `.cache/analysis/a2cd390a4ddb6c33dcdbd2919bdbdea97eb28eeb54edb00bf6c14664040379b4.pkl` | 50 | Analysis cache. Size/fingerprint inspection; not deserialized. |

## Root files

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `.env` | 4,979 | Environment settings; 41 names inspected; values withheld. |
| `.env.example` | 2,769 | Environment settings; 23 names inspected; values withheld. |
| `Autonomous_Data_Science_Agent_Roadmap.md` | 9,169 | Project architecture/features/setup/roadmap documentation; current-vs-proposed differences in PROJECT_REVIEW.md. |
| `COMPLETE_NEW_README.md` | 16,882 | Project architecture/features/setup/roadmap documentation; current-vs-proposed differences in PROJECT_REVIEW.md. |
| `README.md` | 31,301 | Project architecture/features/setup/roadmap documentation; current-vs-proposed differences in PROJECT_REVIEW.md. |
| `ds_agent.db` | 151,552 | SQLite, read-only inspection: projects (78 rows), model_leaderboard (25 rows), reports (55 rows), chat_messages (25 rows), experiments (2 rows). |
| `requirements.txt` | 929 | Python dependency list; missing packages required by current AutoML implementation. |
| `schema.sql` | 1,658 | PostgreSQL schema for projects, models, reports and chat; no experiments migration or access-policy definitions. |
| `test_all_5_datasets.py` | 6,161 | 158 lines. test_all_5_datasets.py — Autonomous Multi-Dataset Verification Suite Definitions: test_file, main. |
| `test_all_services.py` | 2,269 | 53 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `test_analyst_pipeline.py` | 4,419 | 115 lines. Python application/module or verification script. Definitions: run_test. |
| `test_classification.py` | 843 | 17 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `test_live_api.py` | 3,591 | 97 lines. test_live_api.py — Verify Live API Endpoints on http://127.0.0.1:8000 Definitions: test_live. |
| `test_master_suite.py` | 12,266 | 320 lines. Master End-to-End Test Suite for Autonomous Data Science Agent Definitions: record. |
| `test_pipeline_3_datasets.py` | 1,413 | 34 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `test_upload_endpoint.py` | 427 | 11 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `verify_servers.py` | 1,013 | 23 lines. Python application/module or verification script. Executes page/module logic at top level. |

## artifacts

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `artifacts/datasets_0c10508c-b58b-42a3-9da9-18fa881df9bf_Iris Unsupervised.csv` | 2,621 | Dataset: 150 rows x 4 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_22852f51-1e8f-46de-9d8e-ed2c6bf94bbf_Iris Unsupervised.csv` | 2,621 | Dataset: 150 rows x 4 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_312843a2-34a2-47bf-b4c9-3c730c59d8ee_California Housing.csv` | 185,425 | Dataset: 2,000 rows x 9 columns; 0 missing cells; 0 duplicate rows. |
| `artifacts/datasets_35731345-0c30-4caa-a5e6-94cf9a5716a3_Iris Classification.csv` | 2,928 | Dataset: 150 rows x 5 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_3b6ca4a3-9098-4bde-97e6-dff0d531ab63_California Housing.csv` | 185,425 | Dataset: 2,000 rows x 9 columns; 0 missing cells; 0 duplicate rows. |
| `artifacts/datasets_3e747f54-a572-4da4-a3e0-4a93767d8845_Iris Flower.csv` | 2,928 | Dataset: 150 rows x 5 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_3f46f10e-bb6a-4f09-90c9-74c0d6102266_Titanic-Dataset.csv` | 62,894 | Dataset: 891 rows x 12 columns; 866 missing cells; 0 duplicate rows. |
| `artifacts/datasets_5173f2c7-b1f1-446c-b82b-aad737e4e094_Iris Unsupervised.csv` | 2,621 | Dataset: 150 rows x 4 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_5575e6ba-4a21-4ad8-9743-dc857c0c563a_California Housing.csv` | 185,425 | Dataset: 2,000 rows x 9 columns; 0 missing cells; 0 duplicate rows. |
| `artifacts/datasets_583baec4-076a-41e0-99b8-905175b4a2df_Iris Classification.csv` | 2,928 | Dataset: 150 rows x 5 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_63cd380a-0a10-425b-800e-e34bd2e9d10c_Iris Classification.csv` | 2,928 | Dataset: 150 rows x 5 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_78a3b0e7-6cc9-4521-830f-c32c22ce64e8_Iris Unsupervised.csv` | 2,621 | Dataset: 150 rows x 4 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_9ff375db-9659-4259-847c-c0187e167629_California Housing.csv` | 185,425 | Dataset: 2,000 rows x 9 columns; 0 missing cells; 0 duplicate rows. |
| `artifacts/datasets_b9aaf62f-9311-4f3e-8663-47da7e2b320f_Iris Classification.csv` | 2,928 | Dataset: 150 rows x 5 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_c499ac1b-02e2-48c4-a1d8-8500278d13cc_Iris Classification.csv` | 2,928 | Dataset: 150 rows x 5 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_d7afa8df-6a81-4559-9089-1e4671444cdb_Iris Unsupervised.csv` | 2,621 | Dataset: 150 rows x 4 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/datasets_e89188fc-50a9-4bce-95e9-9640135e8c69_California Housing.csv` | 92,675 | Dataset: 1,000 rows x 9 columns; 0 missing cells; 0 duplicate rows. |
| `artifacts/datasets_test_proj_001_Global Retail Transactions.csv` | 12,187 | Dataset: 200 rows x 7 columns; 0 missing cells; 1 duplicate rows. |
| `artifacts/models/a1251e00-450e-4a0e-bc36-f8778557e0ad/logistic_regression.joblib` | 5,092 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/bd9523d4-6875-4e42-b83e-79481aba26f0/linear_regression.joblib` | 3,249 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/default_project/logistic_regression.joblib` | 4,289 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_23862/ridge_regression.joblib` | 3,529 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_2502/logistic_regression.joblib` | 4,053 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_35377/ridge_regression.joblib` | 3,897 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_38595/logistic_regression.joblib` | 5,092 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_44540/logistic_regression.joblib` | 5,600 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_51666/ridge_regression.joblib` | 3,529 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_53954/logistic_regression.joblib` | 4,053 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_62862/logistic_regression.joblib` | 5,600 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_6492/ridge_regression.joblib` | 3,529 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_66119/logistic_regression.joblib` | 5,600 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_66959/ridge_regression.joblib` | 3,897 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_83800/logistic_regression.joblib` | 5,092 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_84273/logistic_regression.joblib` | 5,092 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_87611/logistic_regression.joblib` | 4,053 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/suite_automl_97663/ridge_regression.joblib` | 3,897 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/test_class_01/logistic_regression.joblib` | 3,375 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/test_customers-1000_csv/ridge_regression.joblib` | 89,641 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/test_dataset_csv/xgboost.joblib` | 1,749,786 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/test_debug/logistic_regression.joblib` | 5,092 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/test_kc_house_data_csv/xgboost_regressor.joblib` | 265,305 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/test_noisy_regression_2000x13_csv/linear_regression.joblib` | 3,625 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/test_run_01/random_forest_regressor.joblib` | 3,311,133 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models/test_tested_csv/logistic_regression.joblib` | 5,092 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_0c10508c-b58b-42a3-9da9-18fa881df9bf_champion_pca_3-component.pkl` | 923 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_214df79e-b6c9-4719-bb6e-61d709e11d76_random_forest.pkl` | 176,764 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_22852f51-1e8f-46de-9d8e-ed2c6bf94bbf_champion_pca_3-component.pkl` | 923 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_312843a2-34a2-47bf-b4c9-3c730c59d8ee_champion_random_forest.pkl` | 5,419,246 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_35731345-0c30-4caa-a5e6-94cf9a5716a3_champion_random_forest.pkl` | 176,764 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_3b6ca4a3-9098-4bde-97e6-dff0d531ab63_champion_random_forest.pkl` | 5,419,246 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_3e747f54-a572-4da4-a3e0-4a93767d8845_champion_pca_3-component.pkl` | 955 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_5173f2c7-b1f1-446c-b82b-aad737e4e094_champion_pca_3-component.pkl` | 923 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_583baec4-076a-41e0-99b8-905175b4a2df_champion_logistic_regression.pkl` | 826 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_63cd380a-0a10-425b-800e-e34bd2e9d10c_champion_random_forest.pkl` | 176,764 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_78a3b0e7-6cc9-4521-830f-c32c22ce64e8_champion_pca_3-component.pkl` | 923 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_b9aaf62f-9311-4f3e-8663-47da7e2b320f_champion_random_forest.pkl` | 176,764 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_c499ac1b-02e2-48c4-a1d8-8500278d13cc_champion_random_forest.pkl` | 176,764 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_d7afa8df-6a81-4559-9089-1e4671444cdb_champion_random_forest.pkl` | 992,339 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/models_e89188fc-50a9-4bce-95e9-9640135e8c69_champion_random_forest.pkl` | 3,742,069 | Serialized model or prediction bundle. Size/fingerprint inspection; not deserialized. |
| `artifacts/reports_0c10508c-b58b-42a3-9da9-18fa881df9bf_report_0c10508c_iris_unsupervised.txt` | 14,371 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_214df79e-b6c9-4719-bb6e-61d709e11d76_report_214df79e_iris_flower_test.txt` | 9,103 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_22852f51-1e8f-46de-9d8e-ed2c6bf94bbf_report_22852f51_iris_unsupervised.txt` | 8,193 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_312843a2-34a2-47bf-b4c9-3c730c59d8ee_report_312843a2_california_housing.txt` | 8,141 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_35731345-0c30-4caa-a5e6-94cf9a5716a3_report_35731345_iris_classification.txt` | 15,240 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_3b6ca4a3-9098-4bde-97e6-dff0d531ab63_report_3b6ca4a3_california_housing.txt` | 7,197 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_3e747f54-a572-4da4-a3e0-4a93767d8845_report_3e747f54_iris_flower.txt` | 7,515 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_3f46f10e-bb6a-4f09-90c9-74c0d6102266_report_3f46f10e_titanic-dataset.txt` | 17,702 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_5173f2c7-b1f1-446c-b82b-aad737e4e094_report_5173f2c7_iris_unsupervised.txt` | 8,171 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_5575e6ba-4a21-4ad8-9743-dc857c0c563a_report_5575e6ba_california_housing.txt` | 7,939 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_583baec4-076a-41e0-99b8-905175b4a2df_report_583baec4_iris_classification.txt` | 10,821 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_63cd380a-0a10-425b-800e-e34bd2e9d10c_report_63cd380a_iris_classification.txt` | 8,310 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_78a3b0e7-6cc9-4521-830f-c32c22ce64e8_report_78a3b0e7_iris_unsupervised.txt` | 8,739 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_9ff375db-9659-4259-847c-c0187e167629_report_9ff375db_california_housing.txt` | 8,295 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_b9aaf62f-9311-4f3e-8663-47da7e2b320f_report_b9aaf62f_iris_classification.txt` | 14,950 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_c499ac1b-02e2-48c4-a1d8-8500278d13cc_report_c499ac1b_iris_classification.txt` | 7,548 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_d7afa8df-6a81-4559-9089-1e4671444cdb_report_d7afa8df_iris_unsupervised.txt` | 15,621 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_e89188fc-50a9-4bce-95e9-9640135e8c69_report_e89188fc_california_housing.txt` | 9,690 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/reports_test_proj_001_analyst_report_test_pro_global_retail_transactions.txt` | 7,970 | Historical generated report or text fallback; read and fingerprinted. |
| `artifacts/test_uploads_265aea7f_test.csv` | 53 | Dataset: 2 rows x 3 columns; 0 missing cells; 0 duplicate rows. |

## backend

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `backend/__init__.py` | 40 | Python package marker or agent export list. |
| `backend/agents/__init__.py` | 909 | Python package marker or agent export list. |
| `backend/agents/csv_loader.py` | 3,890 | 100 lines. Python application/module or verification script. Definitions: load_file_dataframe, csv_loader_node, _bg_sync. |
| `backend/agents/diagnostic_agent.py` | 15,289 | 296 lines. diagnostic_agent.py — Root Cause & Diagnostic Agent Definitions: diagnostic_agent_node. |
| `backend/agents/eda_agent.py` | 15,661 | 316 lines. eda_agent.py — Exploratory Data Analysis Agent Definitions: _classify_skewness, _classify_kurtosis, _compute_normality, _compute_mutual_information, eda_agent_node. |
| `backend/agents/hypothesis_agent.py` | 11,390 | 236 lines. hypothesis_agent.py — Statistical Hypothesis Testing Agent Definitions: _select_test_type, hypothesis_agent_node. |
| `backend/agents/kpi_agent.py` | 20,707 | 428 lines. kpi_agent.py — Business KPI & Domain Metrics Agent Definitions: detect_domain, compute_saas_kpis, compute_ecommerce_kpis, compute_ops_kpis, _compute_core_kpi, kpi_agent_node. |
| `backend/agents/quality_agent.py` | 18,025 | 330 lines. quality_agent.py — Data Health & Quality Audit Agent Definitions: _check_negative_values, quality_agent_node. |
| `backend/agents/report_agent.py` | 16,557 | 403 lines. Python application/module or verification script. Definitions: clean_reportlab_xml, generate_analyst_pdf_report, report_agent_node, _bg_report_sync. |
| `backend/agents/schema_agent.py` | 5,711 | 141 lines. Python application/module or verification script. Definitions: schema_agent_node. |
| `backend/agents/supervisor.py` | 4,350 | 108 lines. Python application/module or verification script. Definitions: supervisor_node. |
| `backend/agents/trend_agent.py` | 26,971 | 593 lines. trend_agent.py — Time-Series Intelligence Agent Definitions: _find_date_column, _compute_time_series, _compute_stl_decomposition, _compute_mann_kendall, _compute_seasonality_by_month, trend_agent_node. |
| `backend/agents/visualization_agent.py` | 12,376 | 269 lines. visualization_agent.py — Smart Evidence Chart Generator (Phase 2 Upgrade) Definitions: visualization_agent_node, _add_chart. |
| `backend/config.py` | 4,637 | 78 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `backend/graph/__init__.py` | 38 | Python package marker or agent export list. |
| `backend/graph/state.py` | 1,998 | 71 lines. Python application/module or verification script. Definitions: AgentState. |
| `backend/graph/workflow.py` | 8,335 | 194 lines. Python application/module or verification script. Definitions: create_analyst_graph, run_analyst_pipeline. |
| `backend/main.py` | 27,947 | 650 lines. Python application/module or verification script. Definitions: AnalyzeRequest, ChatRequest, CleanRequest, AutoMLRequest, PredictRequest, root, get_sample_datasets, load_sample_dataset, upload_dataset, analyze_dataset, conversational_analyst_chat, profile_uploaded_dataset. |
| `backend/reports/test_exec_deck.pptx` | 39,536 | Generated analytical deck: 8 slides; XML/text inspected, not visual layout QA. |
| `backend/services/__init__.py` | 41 | Python package marker or agent export list. |
| `backend/services/automl_engine.py` | 25,206 | 587 lines. automl_engine.py — Comprehensive Multi-Algorithm AutoML Engine Definitions: detect_target_and_task, build_preprocessor, get_candidate_models, tune_best_model_with_optuna, run_automl, predict_with_saved_model, objective. |
| `backend/services/cleaner.py` | 6,126 | 155 lines. cleaner.py — Intelligent Data Cleaning Service Definitions: clean_column_names, clean_dataset. |
| `backend/services/experiment_tracker.py` | 4,909 | 146 lines. experiment_tracker.py — Experiment Tracking & Reproducibility Definitions: init_db, compute_dataset_hash, log_experiment, get_project_experiments. |
| `backend/services/job_queue.py` | 7,817 | 224 lines. job_queue.py — Background Job Queue with Status Tracking Definitions: JobStatus, Job, JobQueue, __init__, submit, _run_job, update_progress, get_status, get_result, _cleanup_expired. |
| `backend/services/llm_service.py` | 7,269 | 188 lines. Python application/module or verification script. Definitions: KeyPool, _call_openai_compatible_endpoint, invoke_llm, __init__, get_key, mark_cooldown. |
| `backend/services/profiler.py` | 24,852 | 517 lines. profiler.py — Deterministic Dataset Profiler Service Definitions: _classify_column, _detect_outliers, _compute_distribution, _detect_potential_targets, _compute_correlation_matrix, _build_anomaly_bar_data, profile_dataset. |
| `backend/services/quota_key_pool.py` | 8,009 | 209 lines. quota_key_pool.py — Quota-Aware LLM API Key Pool with Cooldowns Definitions: KeyStats, QuotaAwareKeyPool, is_available, cooldown_remaining, success_rate, idle_seconds, __init__, get_key, report_success, report_failure, health_report, __len__. |
| `backend/services/r2_service.py` | 4,781 | 134 lines. Python application/module or verification script. Definitions: R2StorageService, __init__, get_public_url, upload_bytes, upload_file, upload_dataframe_csv, upload_model_pkl, upload_pdf_report, download_bytes. |
| `backend/services/serializer.py` | 2,163 | 73 lines. serializer.py — Universal JSON Sanitizer Definitions: sanitize_for_json. |
| `backend/services/supabase_service.py` | 7,704 | 208 lines. Python application/module or verification script. Definitions: DatabaseService, __init__, _init_local_db, save_project, save_model_leaderboard, save_report, save_chat_message. |
| `backend/services/xai_service.py` | 5,350 | 142 lines. xai_service.py — Explainable AI (XAI) & Interpretability Service Definitions: compute_feature_importance. |
| `backend/tools/__init__.py` | 59 | Python package marker or agent export list. |
| `backend/tools/benchmarks.py` | 18,421 | 513 lines. benchmarks.py — Industry Benchmark Library (Phase 3) Definitions: get_benchmarks_for_domain, evaluate_metric_vs_benchmark, run_full_benchmark_audit. |
| `backend/tools/caching.py` | 3,711 | 117 lines. caching.py — High-Performance Analysis & Query Caching Layer (Phase 4) Definitions: compute_dataset_fingerprint, get_cached_result, set_cached_result, clear_cache. |
| `backend/tools/charts.py` | 19,890 | 548 lines. charts.py — Smart Chart Library (Phase 2 Upgrade) Definitions: save_fig_json, create_time_series_chart, create_pareto_chart, create_waterfall_chart, create_bar_comparison, create_correlation_heatmap, create_mom_growth_chart, create_trend_decomposition_chart, create_seasonality_chart, create_distribution_chart, create_box_comparison, smart_chart_selector. |
| `backend/tools/comparator.py` | 17,885 | 372 lines. comparator.py — Multi-Dataset Comparison Engine (Phase 3) Definitions: compare_datasets, _generate_comparative_narrative. |
| `backend/tools/pptx_exporter.py` | 24,729 | 606 lines. pptx_exporter.py — Executive PowerPoint Report Generator (Phase 3) Definitions: _add_slide, _set_bg, _add_textbox, _add_divider, _add_bullet_list, _add_table_slide, _build_title_slide, _build_health_slide, _build_kpi_slide, _build_benchmark_slide, _build_trend_slide, _build_diagnostic_slide. |
| `backend/tools/python_tool.py` | 2,146 | 67 lines. Python application/module or verification script. Definitions: execute_python. |
| `backend/tools/sql_tool.py` | 1,752 | 51 lines. Python application/module or verification script. Definitions: execute_sql. |
| `backend/tools/stats_tools.py` | 30,447 | 717 lines. stats_tools.py — Deterministic Statistical Computation Layer Definitions: detect_outliers_iqr, detect_outliers_zscore, detect_outliers_combined, compute_descriptive_stats, compute_group_aggregates, compute_mom_yoy, compute_hhi, two_sample_ttest, mannwhitney_test, one_way_anova, chi_square_test, pareto_analysis. |

## catboost_info

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `catboost_info/catboost_training.json` | 10,239 | Generated CatBoost training log, event record or temporary intermediate. |
| `catboost_info/learn/events.out.tfevents` | 5,398 | Generated CatBoost training log, event record or temporary intermediate. |
| `catboost_info/learn_error.tsv` | 1,643 | Generated CatBoost training log, event record or temporary intermediate. |
| `catboost_info/time_left.tsv` | 885 | Generated CatBoost training log, event record or temporary intermediate. |
| `catboost_info/tmp/cat_feature_index.ef5cab2f-6e36aa70-562b3cd3-fa1231ee.tmp` | 4 | Generated CatBoost training log, event record or temporary intermediate. |

## data

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `data/enterprise_demo.sqlite` | 163,840 | SQLite, read-only inspection: customers (120 rows), products (30 rows), orders (1,500 rows). |
| `data/test_clean_sales.csv` | 57,993 | Dataset: 600 rows x 11 columns; 0 missing cells; 0 duplicate rows. |
| `data/test_noisy_sales.csv` | 51,987 | Dataset: 605 rows x 10 columns; 185 missing cells; 5 duplicate rows. |

## frontend

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `frontend/app.py` | 6,145 | 181 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `frontend/pages/01_📥_Upload_&_Audit.py` | 6,856 | 147 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `frontend/pages/02_🩺_Health_&_KPIs.py` | 8,362 | 165 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `frontend/pages/03_🔍_Root_Cause_&_Hypotheses.py` | 6,202 | 110 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `frontend/pages/04_📈_Visual_Evidence.py` | 1,155 | 32 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `frontend/pages/05_💬_Conversational_Analyst.py` | 17,586 | 364 lines. 05_💬_Conversational_Analyst.py — Phase 2 Upgrade Definitions: _build_analysis_context. |
| `frontend/pages/06_📄_Executive_Briefing.py` | 7,490 | 143 lines. Python application/module or verification script. Executes page/module logic at top level. |
| `frontend/pages/07_⚖️_Dataset_Comparison.py` | 17,323 | 346 lines. Python application/module or verification script. Executes page/module logic at top level. |

## frontend_web

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `frontend_web/.env` | 35 | Environment settings; 1 names inspected; values withheld. |
| `frontend_web/.gitignore` | 253 | Frontend ignore rules for dependencies/build/log/editor files; does not cover root credentials. |
| `frontend_web/dist/assets/index-Dd7_Givg.css` | 11,948 | Generated frontend build bundle or copied static asset. |
| `frontend_web/dist/assets/index-abF3zhsQ.js` | 88,981 | Generated frontend build bundle or copied static asset. |
| `frontend_web/dist/assets/rolldown-runtime-hePW80VL.js` | 716 | Generated frontend build bundle or copied static asset. |
| `frontend_web/dist/assets/vendor-motion-Bh-fi16x.js` | 146,656 | Generated frontend build bundle or copied static asset. |
| `frontend_web/dist/assets/vendor-plotly-CbFL_8dd.js` | 4,675,909 | Generated frontend build bundle or copied static asset. |
| `frontend_web/dist/assets/vendor-react-CIPMNqzC.js` | 230,782 | Generated frontend build bundle or copied static asset. |
| `frontend_web/dist/assets/vendor-three-C64-2LTf.js` | 910,653 | Generated frontend build bundle or copied static asset. |
| `frontend_web/dist/favicon.svg` | 9,522 | Generated frontend build bundle or copied static asset. |
| `frontend_web/dist/icons.svg` | 5,031 | Generated frontend build bundle or copied static asset. |
| `frontend_web/dist/index.html` | 1,027 | Generated frontend build bundle or copied static asset. |
| `frontend_web/index.html` | 508 | HTML entry that loads the React app. |
| `frontend_web/package-lock.json` | 174,966 | npm resolved dependency lockfile. |
| `frontend_web/package.json` | 797 | Frontend dependencies and dev/build/preview scripts. |
| `frontend_web/public/favicon.svg` | 9,522 | Static vector icon/logo asset; Vite/TypeScript logos belong to the unused starter. |
| `frontend_web/public/icons.svg` | 5,031 | Static vector icon/logo asset; Vite/TypeScript logos belong to the unused starter. |
| `frontend_web/src/App.jsx` | 5,196 | Frontend source/configuration: App.jsx. 159 lines. See PROJECT_REVIEW.md for integration findings. |
| `frontend_web/src/api.js` | 4,297 | Frontend source/configuration: api.js. 115 lines. See PROJECT_REVIEW.md for integration findings. |
| `frontend_web/src/assets/hero.png` | 13,057 | Hero image used only by unused TypeScript starter entry. |
| `frontend_web/src/assets/typescript.svg` | 1,303 | Static vector icon/logo asset; Vite/TypeScript logos belong to the unused starter. |
| `frontend_web/src/assets/vite.svg` | 8,709 | Static vector icon/logo asset; Vite/TypeScript logos belong to the unused starter. |
| `frontend_web/src/components/GaugeChart.jsx` | 6,016 | Frontend source/configuration: GaugeChart.jsx. 189 lines. See PROJECT_REVIEW.md for integration findings. |
| `frontend_web/src/components/Sidebar.jsx` | 5,112 | Frontend source/configuration: Sidebar.jsx. 130 lines. See PROJECT_REVIEW.md for integration findings. |
| `frontend_web/src/components/StatCard.jsx` | 3,480 | Frontend source/configuration: StatCard.jsx. 108 lines. See PROJECT_REVIEW.md for integration findings. |
| `frontend_web/src/counter.ts` | 274 | Unused Vite/TypeScript starter code; active app entry is main.jsx. |
| `frontend_web/src/index.css` | 19,643 | Frontend source/configuration: index.css. 738 lines. See PROJECT_REVIEW.md for integration findings. |
| `frontend_web/src/main.jsx` | 229 | Frontend source/configuration: main.jsx. 10 lines. See PROJECT_REVIEW.md for integration findings. |
| `frontend_web/src/main.ts` | 2,464 | Unused Vite/TypeScript starter code; active app entry is main.jsx. |
| `frontend_web/src/pages/AutoMLPage.jsx` | 19,405 | Model competition, leaderboard, explanations and what-if predictions. |
| `frontend_web/src/pages/ChatPage.jsx` | 9,705 | Dataset chat and calculation evidence. |
| `frontend_web/src/pages/EDAPage.jsx` | 11,817 | Distribution, categorical and evidence charts. |
| `frontend_web/src/pages/InsightsPage.jsx` | 6,994 | Business/statistical narrative display. |
| `frontend_web/src/pages/OverviewPage.jsx` | 24,174 | Profile metrics, charts and AI analysis launch. |
| `frontend_web/src/pages/QualityPage.jsx` | 8,331 | Health, missing values and anomalies. |
| `frontend_web/src/pages/ReportPage.jsx` | 3,968 | Executive summary, report text and PDF link. |
| `frontend_web/src/pages/UploadPage.jsx` | 12,781 | Dataset upload, sample loading and profiling. |
| `frontend_web/src/style.css` | 5,060 | Unused Vite/TypeScript starter code; active app entry is main.jsx. |
| `frontend_web/src/useStore.jsx` | 3,448 | Frontend source/configuration: useStore.jsx. 104 lines. See PROJECT_REVIEW.md for integration findings. |
| `frontend_web/tsconfig.json` | 560 | TypeScript settings; JSONC comments are valid. |
| `frontend_web/vite.config.js` | 860 | Frontend source/configuration: vite.config.js. 31 lines. See PROJECT_REVIEW.md for integration findings. |

## reports

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `reports/analyst_deck_266023c7_regression_5000_noisy_duplicates.pptx` | 39,657 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_65e393f2_customers-1000.pptx` | 38,268 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_7572db4c_dataset.pptx` | 37,634 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_b137307d_noisy_regression_2000x13.pptx` | 39,376 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_bd9523d4_regression_5000_noisy_duplicates.pptx` | 39,629 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_clean_te_pristine_retail_sales.pptx` | 41,657 | Generated analytical deck: 8 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_noisy_te_dirty_real-world_sales.pptx` | 38,680 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_session__customers-500000.pptx` | 37,969 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_session__dataset.pptx` | 37,659 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_session__rag_employee_dataset_1000.pptx` | 37,181 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_session__ravenstack_subscriptions.pptx` | 39,995 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_session__test_noisy_sales.pptx` | 41,846 | Generated analytical deck: 8 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_suite_pi_customer_directory.pptx` | 38,161 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_suite_pi_king_county_real_estate.pptx` | 39,885 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_suite_pi_salary_regression_benchmark.pptx` | 39,721 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_suite_pi_software_products.pptx` | 38,249 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_suite_pi_titanic_passenger_outcomes.pptx` | 39,341 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_test-pha_retail_global_transactions.pptx` | 40,886 | Generated analytical deck: 8 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_test_cus_customers_benchmark.pptx` | 38,302 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_test_kc__kc_house_sales.pptx` | 39,897 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_test_sal_salary_regression.pptx` | 38,330 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_test_sal_salary_regression_summary.txt` | 6,276 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/analyst_deck_test_sof_software_products.pptx` | 37,617 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_deck_test_tes_titanic_survival.pptx` | 39,518 | Generated analytical deck: 7 slides; XML/text inspected, not visual layout QA. |
| `reports/analyst_report_266023c7_regression_5000_noisy_duplicates.pdf` | 10,068 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_65e393f2_customers-1000.pdf` | 7,908 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_7572db4c_dataset.pdf` | 6,420 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_b137307d_noisy_regression_2000x13.pdf` | 10,624 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_bd9523d4_regression_5000_noisy_duplicates.pdf` | 11,257 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_bench_01_sales.pdf` | 9,124 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_clean_te_pristine_retail_sales.pdf` | 10,918 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_noisy_te_dirty_real-world_sales.pdf` | 8,392 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_session__customers-500000.pdf` | 6,313 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_session__dataset.pdf` | 6,536 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_session__ravenstack_subscriptions.pdf` | 10,460 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_session__test_noisy_sales.pdf` | 9,819 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_suite_pi_customer_directory.pdf` | 7,032 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_suite_pi_king_county_real_estate.pdf` | 11,018 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_suite_pi_salary_regression_benchmark.pdf` | 9,608 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_suite_pi_software_products.pdf` | 8,432 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_suite_pi_titanic_passenger_outcomes.pdf` | 10,173 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_test-pha_retail_global_transactions.pdf` | 8,710 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_test_cus_customers_benchmark.pdf` | 8,153 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_test_kc__kc_house_sales.pdf` | 10,560 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_test_pro_global_retail_transactions.pdf` | 7,801 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_test_pro_global_retail_transactions.txt` | 7,970 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/analyst_report_test_sal_salary_regression.pdf` | 9,253 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_test_sof_software_products.pdf` | 6,190 | Generated analytical report: 2 pages; extracted text, not visual layout QA. |
| `reports/analyst_report_test_tes_titanic_survival.pdf` | 11,224 | Generated analytical report: 3 pages; extracted text, not visual layout QA. |
| `reports/report_0c10508c_iris_unsupervised.txt` | 14,371 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_214df79e_iris_flower_test.txt` | 9,103 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_22852f51_iris_unsupervised.txt` | 8,193 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_312843a2_california_housing.txt` | 8,141 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_35731345_iris_classification.txt` | 15,240 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_3b6ca4a3_california_housing.txt` | 7,197 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_3e747f54_iris_flower.txt` | 7,515 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_3f46f10e_titanic-dataset.txt` | 17,702 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_5173f2c7_iris_unsupervised.txt` | 8,171 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_5575e6ba_california_housing.txt` | 7,939 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_583baec4_iris_classification.txt` | 10,821 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_63cd380a_iris_classification.txt` | 8,310 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_78a3b0e7_iris_unsupervised.txt` | 8,739 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_9ff375db_california_housing.txt` | 8,295 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_b9aaf62f_iris_classification.txt` | 14,950 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_c499ac1b_iris_classification.txt` | 7,548 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_d7afa8df_iris_unsupervised.txt` | 15,621 | Historical generated report or text fallback; read and fingerprinted. |
| `reports/report_e89188fc_california_housing.txt` | 9,690 | Historical generated report or text fallback; read and fingerprinted. |

## test

| File | Bytes | Purpose / inspection |
|---|---:|---|
| `test/customers-1000.csv` | 171,225 | Dataset: 1,000 rows x 12 columns; 0 missing cells; 0 duplicate rows. |
| `test/dataset.csv` | 297,865 | Dataset: 500 rows x 6 columns; 5 missing cells; 0 duplicate rows. |
| `test/kc_house_data.csv` | 2,515,206 | Dataset: 21,613 rows x 21 columns; 0 missing cells; 0 duplicate rows. |
| `test/noisy_regression_2000x13.csv` | 125,267 | Dataset: 2,000 rows x 13 columns; 60 missing cells; 0 duplicate rows. |
| `test/tested.csv` | 29,474 | Dataset: 418 rows x 12 columns; 414 missing cells; 0 duplicate rows. |

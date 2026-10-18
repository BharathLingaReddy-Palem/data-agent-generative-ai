# First five issue fixes

The chat tool no longer calls Python `exec`. It interprets a limited analytical
language in a disposable subprocess, with `df`, selected pandas/NumPy functions,
aggregations, filters and arithmetic. Imports, arbitrary attribute/function access,
I/O, loops, comprehensions, `apply`, `eval` and `query` are rejected. Assign the final
answer to `result`. Unsupported calculations return a tool error.

Windows starts the worker suspended, assigns it to a Job Object, then resumes it.
The job limits total committed memory, CPU time and process count, and kills its
processes on close. A two-process cap accommodates the Windows virtualenv launcher.
The parent imposes a wall-clock timeout. POSIX uses address-space and CPU rlimits.
Default limits: 15 seconds, 512 MB, 16 MB input, 2 million cells, 16 KB code,
512 syntax nodes, 64 KB printed output and 1 MB serialized result. The worker gets
only a small environment allowlist, with no application credentials. At most two
analytical workers run concurrently per server process. These limits apply to the
chat tool; AutoML and trusted agent computations are separate services.
This is a restricted interpreter, not a facility for arbitrary Python workloads.

Accounts use Argon2 password hashes and expiring, revocable HS256 bearer sessions.
Both React and Streamlit require login. All application API endpoints require a
bearer token except registration/login. Project, model, experiment and job requests
verify the persisted owner before accessing data. Logout revokes the server session
and clears UI data. React keeps its token in sessionStorage for the browser session;
Streamlit keeps it in server session state. The signing secret must be shared by API
and Streamlit when running on different hosts.

Upload/profile/sample registration creates one UUID, persists its owner immediately,
and reuses that UUID through the loader, reports, chat and training. SQLite is the
local authority even when Supabase mirroring is enabled. Database paths no longer
depend on the working directory. Legacy schema migration first creates a SQLite
backup. Historical orphan references get unowned placeholder projects; ownership
is never guessed. Unowned historical data is not exposed through authenticated APIs.
Dataset sessions/jobs are still in memory and do not survive a server restart.

`requirements.txt` now installs the full model/tuning/explanation stack through
`requirements-ml.txt`, plus scikit-learn, joblib, Excel readers, PowerPoint and auth
dependencies. pandas is constrained below 3 because existing agents expect object
string dtypes. `requirements-dev.txt` adds test tooling. `.env.example` documents
auth, execution limits, CORS, database location and current provider variable names.

Pipeline order is loader → supervisor → schema → quality → (KPI + EDA) → diagnostic
→ (hypothesis + trend) → visualization → report. Independent branches merge only
their own output fields and retain every warning/error. Schema's normalized
dataframe reaches quality and subsequent agents.

## Run on Windows

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
# In another terminal:
.venv\Scripts\python.exe -m streamlit run frontend/app.py
# Or run npm run dev from frontend_web.
```

Create an account in either UI. Passwords must have 12–128 characters. API clients
register with `POST /api/auth/register`, then login with `POST /api/auth/login`,
both accepting JSON `{ "username": "...", "password": "..." }`. Send the returned
`access_token` as `Authorization: Bearer <token>`. `/api/auth/me` reads the account;
`POST /api/auth/logout` revokes the session. `AUTH_ALLOW_REGISTRATION=false` disables
new accounts once the required users exist. Set a random secret of at least 32
characters on servers; blank configuration creates a persistent local key.

Cloud syncing is disabled by default. For a cloud mirror, apply `schema.sql`, use a
server service-role key, and keep bucket access private. Existing public R2 objects
are outside API ownership checks. Cloud credentials and live provider requests are
not exercised by the offline regression suite.

## Validate

```powershell
.venv\Scripts\python.exe -m pytest -q
# From frontend_web:
npm run build
```

The suite uses a temporary database, prevents provider HTTP requests, tests
cross-user/revoked/expired sessions and blocked Python payloads, verifies Windows
worker timeout/memory limits, and exercises realistic CSV data. `tests/data` includes
603 retail rows with returns, duplicates, missing discounts, quoted categories and
UTF-8 text, plus 300 subscription rows, and a known-answer manifest. Five existing
CSV datasets are also uploaded/profiled (200-row samples). The actual retail agent
pipeline generates PDF/PPTX and trend charts with offline LLM responses. Classification
and regression tests train candidate models, reload saved artifacts and predict.

Old manual live API scripts now require `DS_TEST_USERNAME` and `DS_TEST_PASSWORD`
for an account created in the UI. They can call live providers and modify the active
database, so use the offline suite for repeatable checks.

References: [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[FastAPI JWT authentication](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).

## Next five fixes: results, exports and tuning

Concurrent agents now retain warnings appended before an exception, as well as
the exception itself. Merging removes only inherited log entries: separate agents
can report the same warning without either occurrence disappearing. Insights and
Report pages display the pipeline warnings returned by the API.

`POST /api/analyze` and the result of `POST /api/analyze/start` use one JSON builder.
Both include `analysis_plan`, `trend_results`, `benchmark_results`, `eda_insights`,
`executive_report`, `report_artifacts`, `report_pdf_url` and `report_pptx_url`, along
with the existing audit/KPI/diagnostic/hypothesis/chart/log fields. NumPy values and
non-finite numbers are sanitized in both paths. Internal dataframe and filesystem
paths are excluded. A failed quality audit has a null score rather than an invented
perfect score. `report_artifacts.pdf` and `.pptx` each contain `available`,
`download_url`, `filename` and `media_type`; unavailable URLs are null.

Insights now reads the agent's actual field names: `kpi_interpretation`,
`diagnostic_narrative`, `trend_narrative`, `executive_summary`, `tests_conducted`,
and the plan's `reasoning`. A skipped trend shows its recorded reason.

Authenticated owners can download either generated export from
`GET /api/reports/{project_id}/{format}/download`, where `format` is `pdf` or `pptx`.
New files live in `reports/{full-project-id}/executive_report.pdf` and
`executive_presentation.pptx`, independently of the dataset name. Each format is
published atomically after generation, and one export can succeed when the other
fails. Text fallbacks are never advertised as PDF/PowerPoint downloads. The routes
read the last successfully published file from disk, so they work after dataset
sessions are cleared or the server restarts, provided the database and reports
directory are retained. Old flat report files are preserved; rerun an analysis to
create the new project-scoped exports. API file URLs require bearer authentication;
React sends the token through a blob download. Streamlit uses its gated local
download buttons instead of unauthenticated cloud links.

Optuna's winning parameters are applied to a fresh estimator and refit on the
training partition. The leaderboard, held-out metrics, diagnostic predictions and
explanations are refreshed from the estimator actually saved. Selection and tuning
acceptance use cross-validation scores, rather than selecting on held-out metrics.
Failed or worse tuning retains the working baseline and reports `applied: false`
with a reason; the UI distinguishes that from applied tuning. Trial counts are
reported from the actual study. Searches use at most 2,000 training rows; final
refitting and acceptance checks use the complete training partition. Unsupported
models retain their baseline. The saved bundle includes tuning metadata and is
published atomically as `champion.joblib`; downloads and prediction fallback prefer
that file over older model artifacts.

Additional checks cover sync/background response parity, preservation of concurrent
warnings, owner-only downloads after session loss, real PDF/PPTX contents and export
failures, and a real Optuna search whose saved model is checked against its selected
parameters. Regression tests compare predictions and reported metrics after tuning
and verify failed/worse/disabled tuning. From `frontend_web`, run `npm test` for the
Insights contract and authenticated report download checks, then `npm run build`.

## Evaluation, Pareto, benchmark contracts and cleaning

AutoML now cross-validates complete sklearn pipelines. Each fold learns its own
feature selection, imputation, scaling, category encoding and optional IQR clipping.
The winner and Optuna parameters are selected using training-fold scores; only the
frozen winner is evaluated on the 20% holdout. Other leaderboard entries contain CV
scores, with empty holdout cells in React. The API reports actual `cv_folds`,
`cv_metric` and split sizes. Classification selection and primary holdout scoring
both use `f1_macro`; `f1_weighted` is separate, and the legacy `f1_score` field is now
an alias of macro F1. Precision and recall use macro averaging. Experiment records
name the primary metric explicitly. Existing saved models and historical experiment
metrics are unchanged; retrain to obtain the corrected evaluation.

Pareto includes the category that first reaches or crosses 80%. Zero totals and
negative contributions return an explicit error instead of a misleading share.

Benchmarks require an exact `metric_key`, finite `value`, `unit` and `period`.
No fuzzy column matching or fallback from a missing mean to a total is performed.
For example, a retail margin can use
`{"metric_key":"profit_margin_pct","value":18,"unit":"%","period":"reporting_period"}`.
Monthly churn requires `%/mo` and `monthly`; annual rates require `%/yr` and `annual`.
Ratios, currency amounts, unknown periods and incompatible units are skipped with
a reason. Zero is a valid observation. The computed retail profit margin supplies
its own explicit metadata, and report audits include derived domain KPIs. Generic
churn observations do not imply a monthly period. The existing historical reference
thresholds are marked unverified, and no percentile is inferred from those cutoffs.

Column trimming at ingestion and snake-case cleaning both generate deterministic,
unique names, including collisions with existing suffixes. `POST /api/clean` accepts
`target_column` and preserves that column's values, missing labels and outliers.
Without a known target, cleaning performs only structural changes. The response
includes current columns and a refreshed profile. Profile, analysis and chat use
the active analytical view; Streamlit chat and active-dataset comparison use it too.
Cleaning clears cached analysis/model results and requires retraining before
prediction or downloading the prior model in that session.

Model fitting replays structural cleaning from the source and learns numeric
imputation and clipping within training folds, avoiding statistics computed over
the full cleaned dataset. Selecting a different target rebuilds the analytical view
with that target protected. The saved pipeline applies the same feature conversions
and fitted transformations at prediction time, including numeric category inputs.

Invalid explicit targets now fail before a background job is submitted. AutoML
requires at least 20 labeled rows, two distinct target values and usable non-ID
features. Classification requires at least five observations per class, at most 20
classes and sufficient holdout capacity; rare classes are never merged. Regression
requires finite numeric labels, which are never imputed. Identifier tokens are
excluded for numeric and categorical features, and there is no fallback that adds
them back. Excluded features, missing-label counts and model failures are returned.
`POST /api/automl/start` accepts an optional `task_type` of `classification` or
`regression`, also exposed in React for ambiguous integer outcomes. Automatic
splitting remains random (stratified for classification); temporal or grouped
evaluation is not implemented by these changes.

Focused tests exercise fold isolation, winner-only holdout evaluation, imbalanced
F1 labels, Pareto crossings, incompatible benchmark contracts, header collisions,
protected/changing targets, active API views, source-data replay, validation errors
and saved-model prediction conversions. The existing full-catalog CSV training,
actual report generation and offline security checks remain part of the suite.

Verified after these fixes: 122 Python tests passed, 3 frontend tests passed,
Python compilation passed and the Vite production build passed. Existing dependency
deprecation warnings and the Plotly bundle-size warning remain.

## Samples, frontend state, statistics and durable jobs

All three sample APIs now return a complete deterministic profile computed over
600 rows. React consumes that profile, and Streamlit downloads the full owned CSV
instead of treating the ten-row preview as the dataset. Sample generation uses
a local random generator. Invalid sample names and rejected requests produce an
error rather than silently substituting another dataset.

React chat, AutoML configuration/results, predictions and job polling live in the
shared provider, so page navigation preserves them. Changing projects resets
derived state. Project/job IDs and upload tokens guard against late async results
from old datasets or jobs. Polling aborts on dataset changes/logout; browser reload
restores the selected project's saved results, messages and pending work. AutoML
training and prediction now use the same `VITE_API_URL` client and bearer token as
the rest of the app; `frontend_web/.env.example` documents separate deployment.
Streamlit clears analysis, conversation and comparison state when loading another
dataset and saves uploaded datasets to the shared durable store.

Box charts use explicit full-data quartiles and observed whiskers inside 1.5 IQR
fences, retaining legitimate zero values. Histograms display actual bin counts;
legacy percentile summaries become quantile curves instead of fake frequencies.
Outlier agreement intersects observation masks, including duplicate dataframe
indexes; matching counts alone do not establish agreement or data errors.
Normality non-rejection is no longer described as proof of normality. Hypothesis
families and dataset comparisons use Holm-adjusted p-values. Comparisons declare
Welch's test on per-record means as primary; a significant Mann-Whitney sensitivity
test cannot override it or validate changes in aggregate totals. Undefined tests
are unavailable, and sparse chi-square tables or invalid group/sample counts fail
explicitly. Effect sizes preserve zero and Welch's Cohen's d uses pooled degrees
of freedom. These exploratory tests assume independent observations and do not
establish causation or practical importance.

Seasonality requires at least two complete annual cycles and adequate estimated
STL strength. One year's month-to-month differences and constant series cannot
establish recurrence. Monthly summaries use mean monthly totals. Missing months
remain gaps; STL/trend testing declines such inputs and MoM does not fill missing
observations or turn undefined growth into zero. Mann-Kendall variance includes
tie correction and declares its independence/autocorrelation limitations.

Dataset snapshots use compressed JSON with explicit dataframe/date/non-finite
codecs, avoiding executable deserialization. SQLite stores owner-bound sessions
and job descriptors, status, stage logs and results. LRU eviction reloads sessions
from disk. The bounded thread pool replaces an unbounded thread/queue model, and
pipeline/AutoML callbacks report actual completed stages rather than timers.
Queued analysis/AutoML descriptors resume on API startup; interrupted running jobs
are retained as failed with an explicit retry message. Use one API process
(`--workers 1`); distributed/multi-process workers are not supported.

Enforced defaults: 10 MiB upload; 100,000 rows; 128 columns; 2 million cells;
100 MiB decoded dataset memory; eight cached sessions; 20 stored sessions per user
and 100 MiB compressed snapshots per user; three worker threads; 12 pending jobs
globally; three per user; one per project. Oversized content, including chunked
multipart requests and expanded Excel data, returns 413. Session/job admission
returns 429, and queued/running projects cannot be cleaned or removed (409).
Terminal job history is pruned at startup/submission to 200 records/seven days.
Configure these values in `.env.example`. GET `/api/projects` and
`/api/projects/{id}/session` expose owned saved work; DELETE `/api/projects/{id}`
frees session quota and metadata after pending work finishes. Generated artifacts
remain on disk and need separate retention management.

New tests cover all sample profiles/full CSVs, owner isolation, typed snapshots,
cache eviction, quotas, real child-process interruption/recovery, stage progress,
queue admission/failure persistence, byte/row/column/cell/memory/Excel expansion
limits, chunked requests, stale frontend responses, configured backend addresses,
quartile charts, outlier masks, adjusted tests and seasonality/gaps.

Verification for this batch: 151 Python tests and 10 frontend tests passed;
Python compilation and the Vite production build passed. Dependency warnings and
the existing large Plotly bundle warning remain.

## Shared key health, complete fingerprints and maintained verification

LLM calls and `/api/keys/health` now use the same `QuotaAwareKeyPool` instances
from `llm_service.py`. The duplicate monitoring-only pools and separate legacy
round-robin implementation were removed. Each actual attempt records success or
failure. Health includes attempts, successes, failures, in-flight counts, rate-limit
hits and cooldowns; success rate is null before the first attempt. Cooling keys
are skipped instead of being reused when all keys are exhausted. Rate limits
apply 65 seconds, transport/5xx failures 15 seconds and 401/403 one hour. A late
concurrent error cannot shorten an existing longer cooldown. Reads do not probe
providers or expose full key credentials. Counters are local to the API process,
reset on restart and do not represent provider billing quotas or calls made by a
separate Streamlit process.

Experiments and cache helpers share `dataset_fingerprint.py`, a versioned SHA-256
digest of every row, typed values, full floating-point precision, index, schema,
categorical metadata and row/column order. It streams rows rather than building a
second whole-data JSON snapshot. Middle-row changes now invalidate both hashes.
Cache query strings preserve literal case and whitespace. Unsupported data raises
an explicit TypeError instead of returning the shared `unhashed` placeholder.
Version tags invalidate previous sampled cache keys; historical experiment hashes
remain unchanged. Experiment history responses now include `dataset_hash`.

`run_regression.py --frontend` runs the offline pytest suite and Node tests, with
nonzero exit codes for assertion, collection, no-tests or frontend failures. The
six old local demonstration scripts now delegate to it. Explicit live smoke
scripts remain separate; the upload check uses current profile fields, asserts
status/content and no longer swallows errors. The live job check fails clearly
when its polling deadline expires. No live provider checks were performed in
this batch.

The README now describes the executed stage pipeline, configured key slots,
supervised-only AutoML, exploratory statistics, actual storage/recovery behavior,
local experiment history, and the difference between installed helpers and active
features. It removes unsupported claims of guaranteed correctness/latency,
automatic analysis caching, mutual information, DuckDB-backed API execution,
provisioned 18-key quotas and production completeness. Older architecture/free-tier
guides and folder inventories are marked historical, preserving their content
without presenting their assumptions as current setup instructions.

Verification: the full maintained runner passed 187 Python tests and all 10
frontend tests. After adding the final concurrent-cooldown regression, the focused
key-health suite passed all 12 cases (188 distinct Python cases verified across
the full and final focused runs). Python compilation passed. New coverage follows
mock HTTP outcomes through the live health API, tests cooldown/failover/recovery,
checks concurrency counters, middle-row and precision/schema/index changes, tests
real memory/disk cache misses, and executes an intentionally failing subprocess
to verify that the regression runner exits nonzero. Existing dependency warnings
remain.

## Real Kaggle datasets and file-format verification (9 October 2026)

Added a bounded, explicit Kaggle downloader with a source/checksum manifest and a
private `KAGGLE_API_TOKEN` setting. Seven real files now cover Iris, wine quality,
Titanic, airline passengers, bank churn, insurance and air quality. Regression
tests use full files for upload/profile/download equality, complete analysis and
PDF/PPTX downloads. Five full-file competitions use actual installed estimators,
save models, verify prediction/session recovery and reject cross-user access.
Separate checks calculate the air-passenger total through the restricted chat
subprocess and reject a dataset with no usable supervised features.

File testing exposed UTF-8/comma-only ingestion and silent handling of ragged
records. The shared parser now handles common BOM/Windows encodings, alternate
delimiters and decimal commas, validates CSV records before pandas inference and
retains all upload/dataset limits. The direct loader and Streamlit comparison
page use these same rules, removing the loader's bad-line skipping fallback.

Date inference now precedes identifier classification, requires plausible date
values, recognizes an evidenced day-first convention and preserves uncertain
values. Schema conversion no longer replaces failed date-like text columns with
NaT. Cleaning converts infinite feature values to missing values before selected
imputation and records them in the audit without modifying labels.

Added real CSV/XLS/XLSX export fixtures, corrupt/unsupported file cases, direct
loader parity checks and an authenticated Streamlit rendering check for all eight
screens with a completed pipeline result. The Kaggle regression suite makes no
live LLM/cloud calls. Detailed scope and final verification results are in
[APPLICATION_TEST_REPORT.md](APPLICATION_TEST_REPORT.md).

Final verification: 246 Python tests and 10 Node frontend tests passed with no
failures or skips. The production frontend build, Python compilation, installed
dependency consistency check and all seven downloaded-source checksums passed.
This batch adds 58 regression cases. Nonfatal dependency/deprecation and bundle
size warnings remain, as recorded in the test report.

## Glass workspace redesign (11 October 2026)

Rebuilt React authentication with responsive glass panels, explicit field labels,
password visibility, error/loading feedback and keyboard-accessible workflow
previews. Added a shared emerald/ink surface system, responsive sidebar and mobile
navigation, account sign-out, and Ctrl/Cmd-K page search. Restyled upload/sample
selection and made overview, quality and EDA layouts fit phone screens. Removed
the upload page's WebGL background and lazy-loaded analysis pages so signing in
does not load Plotly. Replaced inert overview report controls and fixed its PDF
action to use authenticated downloads. Signing out or receiving a 401 also clears
the previous account's persisted dataset selection.

Verification: production build and all 11 Node frontend regression tests passed.
Browser checks covered authentication feedback, password visibility, preview tabs,
real sample profiling (600 rows), overview/quality navigation, page search, mobile
menu focus and phone layouts at 390 x 844. Final previews are saved under
artifacts/ui-preview. Plotly still produces a nonfatal bundle-size warning;
backend behavior was not changed or fully retested in this UI batch.

## Light glass workspace and output audit (11 October 2026)

Supersedes the emerald/ink appearance above with a light frosted workspace and a
matching dark option. Added shared responsive chart styling, safe Markdown,
corrected AutoML controls, individual-column box plots, readable probability
labels, saved-project restoration and explicit chat calculation status. Fixed
numeric columns being mistaken for dates, non-additive KPI aggregation and trend
analysis, unsupported narrative patterns, the eight-column quality-check cap,
misleading feature-importance text and Windows SQLite connection cleanup.

Exercised actual CSV upload, 600-row sample profiling, queued analysis, six-model
AutoML with Optuna, what-if prediction, chat calculations, authenticated model /
PDF / PowerPoint downloads, saved-state restoration, theme switching, search and
phone/tablet layouts. Final validation: 263 Python tests and 14 frontend tests
passed; production build, Python compilation and dependency checks passed.
Scope, evidence and remaining limitations are in
[UI_AUDIT_REPORT.md](UI_AUDIT_REPORT.md).

## Ten-source Kaggle browser audit (11 October 2026)

Uploaded and exercised ten full Kaggle datasets through React (39,959 rows),
including mixed types, missing values, duplicates, free text, Boolean labels,
dates, semicolon/decimal-comma CSV and Windows encoding. Fixed identifier-based
correlations, measure/dimension collisions, missing virtual count columns,
inconsistent health scores, unsupported report/date claims, passenger-count
aggregation, export-column target suggestions, transient polling failures,
conflicting analysis/training actions, truncated missing-value charts and
provider-dependent basic chat counts. Expanded source fetching and regression
coverage; local development now uses Vite's configured API proxy.

Final validation: 280 Python tests and 15 frontend tests passed; production build,
dependency checks and compilation passed. All ten final analyses recorded no
pipeline errors. Actual browser downloads produced 10 PDFs, 10 PowerPoint files
and eight trained model artifacts; representative predictions passed. Two
unsupported AutoML inputs return clear validation messages. Dataset quality and
model suitability limitations remain explicit, including weak Superstore holdout
performance and Air Quality sentinel values. Detailed results and evidence:
[KAGGLE_WEB_TEST_REPORT.md](KAGGLE_WEB_TEST_REPORT.md).

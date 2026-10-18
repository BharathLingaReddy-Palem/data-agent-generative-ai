# Application verification — 9 October 2026

The supplied Kaggle credential was saved only in the private root `.env` as
`KAGGLE_API_TOKEN`. Authenticated Kaggle downloads succeeded. The credential is
not included in this report, example configuration or test fixtures.

## Real datasets

Every file below was uploaded in full through the authenticated API, profiled,
downloaded and compared against an independently parsed source dataframe. Each
also completed the actual analysis pipeline and produced downloadable PDF and
PowerPoint files. Another user's access was rejected.

| Kaggle dataset | Rows | Columns | Additional checks |
| --- | ---: | ---: | --- |
| [Iris](https://www.kaggle.com/datasets/uciml/iris) | 150 | 6 | Multiclass classification, saved-model predictions |
| [Red wine quality](https://www.kaggle.com/datasets/uciml/red-wine-quality-cortez-et-al-2009) | 1,599 | 12 | Explicit regression on ordinal quality, saved-model predictions |
| [Titanic](https://www.kaggle.com/datasets/yasserh/titanic-dataset) | 891 | 12 | Classification with missing numeric/categorical inputs |
| [Air passengers](https://www.kaggle.com/datasets/rakannimer/air-passengers) | 144 | 2 | Monthly trends, full-file chat aggregation, saved chat; unsuitable AutoML input rejected |
| [Bank churn](https://www.kaggle.com/datasets/shrutimechlearn/churn-modelling) | 10,000 | 14 | Full-file classification and saved-model predictions |
| [Insurance](https://www.kaggle.com/datasets/mirichoi0218/insurance) | 1,338 | 7 | Mixed-feature regression and saved-model predictions |
| [Air quality](https://www.kaggle.com/datasets/fedesoriano/air-quality-data-set) | 9,471 | 17 | Semicolon delimiter, decimal commas, day-first dates, empty trailing columns/rows |

The five model competitions used all source rows and the installed candidate
catalog, without stubbing estimators, preprocessing or explanations. All candidate
models trained successfully. Tests verify CV selection, holdout metric labels,
model downloads, three-row predictions and prediction equality after clearing the
session cache. Tuning is disabled for these five competitions; the dedicated
Optuna tests separately run real trials and verify saved parameters.

Downloaded source files and SHA-256 checksums are recorded in
`tests/data/kaggle/manifest.json`. Air-quality domain-specific missing-value
sentinels are preserved; the application does not silently reinterpret every
negative value. These source data and exploratory reports need domain review.

## Problems found and fixed

1. CSV imports assumed UTF-8 and commas. Windows-1252 and BOM UTF-16/32 now decode
   correctly. Comma, semicolon, tab and pipe delimiters are detected; numeric
   decimal commas are recognized in non-comma exports.
2. Pandas could silently reinterpret extra fields as an index or accept truncated
   records. A strict CSV scan now rejects inconsistent field counts, broken
   quoting and binary/control characters with a clear client error. Existing
   byte, row, column, cell and memory limits remain enforced.
3. High-cardinality dates and long text were classified as identifiers. Dates are
   recognized first, and identifiers require an appropriate column name.
4. Failed schema date conversion erased non-date text such as clock strings and
   update statuses. Conversion now commits only when date inference succeeds.
   Consistent day-first slash dates are recognized from unambiguous evidence;
   ambiguous or mixed slash conventions are preserved instead of guessed.
5. Cleaning left infinite feature values in place and could use them for
   imputation. With a selected target and missing-value cleaning enabled,
   nonfinite feature values become missing values before imputation, with an
   audit count. Target values remain protected.
6. The direct pipeline loader and Streamlit comparison uploads used different
   parsing rules, including a fallback that skipped bad CSV records. They now
   share the same validated parser as API uploads. Named Excel sheet support is
   retained by the direct loader.

## Coverage and reproduction

`tests/test_file_matrix.py` covers eleven valid CSV/Excel export variants through
the API and direct file/byte loader: UTF-8, UTF-8 BOM, Windows encoding, UTF-16,
semicolon/tab/pipe delimiters, decimal commas, quoted commas/newlines/quotes,
XLSX and a genuine legacy XLS workbook. It also checks eleven invalid/unsupported
files, Excel dates and duplicate/blank headers, infinite features, date preservation
and identifier classification. Resource-limit tests remain in
`tests/test_upload_limits.py`.

`tests/test_kaggle_datasets.py` covers the seven full datasets, actual analyses and
exports, five background model competitions, prediction/session recovery,
ownership and a real isolated chat calculation. Narrative calls are stubbed in
the regression suite, while statistics, charts, models, reports and the restricted
calculation subprocess actually execute.

`tests/test_streamlit_smoke.py` renders the home screen and all seven pages with
an authenticated account and a completed real pipeline result, asserting no
uncaught exceptions. Existing Node tests cover React response rendering, charts,
state transitions, stale responses and restored work.

```powershell
# Requires the private Kaggle credential; download once, not during pytest:
.venv\Scripts\python.exe testing_tools/fetch_kaggle_datasets.py

# Temporary database, blocked external providers, actual local execution:
.venv\Scripts\python.exe run_regression.py --frontend

# Production frontend bundle:
cd frontend_web
npm run build
```

Install `requirements-dev.txt` for pytest, httpx and the XLS fixture writer.
Kaggle tests explicitly skip when downloaded fixtures are absent.

## Final results

- Maintained full runner: **246 Python tests passed**, zero failures or skips,
  in 208.61 seconds; **10 Node frontend tests passed**, zero failures or skips.
- **58 new regression cases** were added in this testing batch.
- Production React build: passed.
- Python compilation: passed for backend, frontend, tests, testing tools and runner.
- `pip check`: no broken requirements found.
- Seven downloaded source files match their recorded byte lengths and SHA-256
  checksums. The private credential is absent from new tests, docs and examples.

The complete runner output is saved locally in `application_regression.log`.
The run emitted 123 nonfatal dependency/deprecation warnings; the production build
also reports large visualization bundles. These did not prevent execution.

Test environment: Python 3.13.5, pandas 2.3.3, NumPy 2.5.3, scikit-learn 1.9.1,
FastAPI 0.143.0, Streamlit 1.65.0, XGBoost 3.4.1, LightGBM 4.7.0, CatBoost 1.2.10
and Optuna 4.9.0. These record the tested environment, rather than promising
identical behavior across other dependency versions.

## Scope

Kaggle authentication and dataset downloads were tested live. Regression runs
use temporary SQLite storage and make no live LLM/cloud calls. They verify the
API via FastAPI's HTTP test client and Streamlit via its application test runner;
they do not constitute a browser-based visual acceptance test, production load
test or an assessment of live LLM answer quality. Existing dependency deprecation
warnings and the large Plotly/Three.js bundle warning are nonfatal.

# Workspace features — implementation and live verification

Verified on 12 October 2026 against the local React frontend and authenticated FastAPI backend.

## Delivered

- **Clean Data:** preview before applying sentinel replacement, explicit type conversion, text trimming, column removal/rename and duplicate removal; target protection; before/after quality and row samples; undo through immutable versions.
- **Train & Compare:** random, grouped and chronological partitions; preprocessing inside training folds; cross-validation selects the winner; final holdout versus a simple baseline; confusion matrices, residual/actual-versus-predicted plots and reliability warnings.
- **Data Explorer:** server-side literal search, sortable/paginated table, multiple filters and clickable category/histogram crossfilters. Charts, row counts and summary statistics share the filtered view.
- **Version History / Saved Runs:** preserved original and cleaned frames, transformation steps and hashes, quality comparisons, version activation/CSV downloads, version-linked model settings/results and distinct model artifacts.
- **Forecasting:** calendar frequency, aggregation, horizon and season settings; explicit missing-period policy; two rolling validation origins plus a separate final holdout; model/baseline comparison and approximate prediction bands.
- **Text Classification:** TF-IDF inside validation pipelines; Logistic Regression and Multinomial Naive Bayes; normalized duplicate messages stay together; per-class scores, confusion matrix, misclassified examples and new-message prediction.
- **Report Builder:** selected evidence charts, editable context/commentary, title/organization/accent branding, saved templates and authenticated PDF/PowerPoint downloads.

The sidebar groups Train & Compare, Forecasting, Text Classification and Saved Runs under **Machine Learning**. These new workflows are implemented in React; Streamlit retains its existing screens.

## Live browser checks

| Workflow | Input and actions | Observed result |
| --- | --- | --- |
| Explorer | Pokemon, 800 rows; search Pikachu; sort names; click Water category | Search returned one row. Water crossfilter returned 112 rows and updated the table, histograms and statistics. |
| Explorer edge case | Search a unique date in the 240-row fixture | One row remained with its numeric histogram, mean and median still visible. |
| Cleaning | 246-row fixture with six duplicates, sentinel -200, whitespace and invalid numeric text | Preview left original unchanged. Applying removed six duplicates, retained 240 rows and replaced the sentinel with missing values. |
| Type conversion / rename | Convert amount_text to number and rename to amount | Strict mode explained the invalid value; explicitly allowing invalid values to become missing enabled preview/apply. |
| Undo / versions | Undo the conversion, then activate the saved converted version | All three versions remained available. Original: 246 rows, quality 90.1; sentinel/dedup: 240 rows, 94.9; converted: 240 rows, 92.3. Quality is a heuristic, not a claim that all changes increase quality. |
| Grouped regression | Cleaned fixture; group account_group, target outcome | Lasso selected by training folds; holdout R² 0.9876 versus baseline -0.0093; 190 training / 50 holdout rows. Diagnostics rendered. |
| Chronological regression | Cleaned fixture; date column, target outcome | Linear Regression holdout R² 0.9860 versus baseline -0.0005; 192 training / 48 holdout rows. Residual and actual-versus-predicted charts rendered. |
| Random classification | Cleaned fixture; target label | Logistic Regression macro F1 1.0000 versus baseline 0.3425; confusion matrix had 25 and 23 correct predictions. |
| Poor future performance | Synthetic 240-row chronological fixture with a +1000 outcome shift in its final 48 rows | Holdout R² -11379.0612; app explicitly warned of poor holdout performance and a substantial validation-to-holdout drop. |
| Forecast | Full Kaggle Air Passengers; monthly mean; season/horizon 12 | Exponential smoothing selected on rolling validation. Separate holdout MAE 13.38 versus seasonal naive 47.83. Future values, bands and holdout chart rendered. |
| Forecast gaps | Air Passengers with one month removed | Reject policy explained the gap. Past-only forward fill completed; filled outcomes were excluded from evaluation and the result disclosed the filled period. |
| Text models | Full Kaggle SMS Spam, 5,572 messages; text v2, target v1 | Logistic model macro F1 0.9568 versus majority baseline 0.4639; 4,457 training / 1,115 holdout rows; per-class evaluation and all 23 errors visible. |
| New text inference | Prize/cash message, then ordinary lunch message | Returned spam, then ham using the saved text model. |
| Run artifacts | Saved grouped/chronological/classification runs | All three remained listed with settings/version and diagnostics; model download succeeded. |
| Custom reports | Two selected charts; edited context/commentary; organization and title | PDF and PowerPoint downloaded. All three PDF pages and five PowerPoint slides were rendered and visually inspected. |
| Templates | Save Model readiness review; restart backend; reload template | Saved branding, commentary, context and chart choices reloaded correctly. |
| Restart recovery | Stop/start backend and reload frontend | Version history, saved models, text/forecast results and specialized workflow settings restored. |
| Responsive layout | Desktop 1280 px; text page 390 px; forecast 320 px | Forms remained usable; mobile navigation worked; document width matched viewport with no page-wide horizontal overflow. Temporary viewport override was reset. |

## Defects found and fixed during live testing

- Explorer metrics attempted to render a row array as a React value, crashing the page.
- Numeric/category defaults did not recognize profiled role names such as numeric_continuous.
- Filtering to one row removed numeric eligibility and hid the histogram/statistics.
- Text and forecast input selections were lost after leaving their pages; settings now persist per project and restore from saved runs after reload.

## Automated checks

- Backend: **289 passed**, 130 warnings, approximately 306 seconds. Includes new ownership, preview/apply/undo, stale revision, type/target protection, grouped/chronological boundaries, persistent versions/templates, baseline/artifact isolation, text, forecasting and custom export checks.
- Frontend: **17 passed**. Includes configured API authentication, project-bound state, stale-response rejection, split/settings requests and report downloads.
- Vite production build: **passed**. A large Plotly bundle warning remains; it is a performance optimization opportunity, not a build failure.

## Practical limits

- Forecast intervals are approximate error bands estimated from two rolling validation origins. They are not calibrated guarantees of 95% future coverage.
- Forecasting currently covers seasonal naive, last-value and additive exponential smoothing, with up to 5,000 regular periods and a 60-period horizon.
- Text classification starts with TF-IDF models, not transformer fine-tuning. Identical normalized text is kept together; this does not detect every near-duplicate or external leakage source.
- Twenty versions and 100 saved runs per project; 30 templates per user. Version frame storage has a default 100 MB compressed quota per user, separate from session snapshots.
- Saved Runs version linkage begins with the new workflow. Older experiment records are not retroactively assigned to versions.
- Report branding supports organization/title/accent color; custom logo upload and free-form slide layouts are not included.
- Checks establish the observed local behavior; they do not establish production load capacity or guarantee model quality on arbitrary datasets.

## Evidence

Artifacts are in `artifacts/workspace-audit/`: live screenshots, test fixtures, downloaded `custom-report.pdf` and `custom-report.pptx`, and rendered report page/slide PNGs. Test data is public Kaggle data or synthetic data.

The app remains available at http://127.0.0.1:5173/ with the backend at http://127.0.0.1:8000/.

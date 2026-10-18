# Guided cleaning and Machine Learning live audit

Date: 18 October 2026. Tested the running React app at http://127.0.0.1:5173/ against the local API, using an existing test account and synthetic fixtures plus the downloaded Kaggle SMS Spam/Air Passengers data. Original uploads and previous runs remain preserved.

## Guided cleaning

The main form now offers selections instead of requiring technical syntax:

- Observed placeholder checkboxes, including `-200`, with occurrence counts. Suggestions are opt-in because a suspicious value can be legitimate.
- Type-aware missing-value choices: keep missing, remove rows, replace with zero/Unknown/true/false as applicable, choose an observed value, or optionally enter a custom value.
- Human-readable date formats with examples; custom format codes are optional.
- Category case selection and source/destination dropdowns, with optional new labels and removable mapping rules.
- Whitespace and exact-duplicate checkboxes, target protection, version names, preview, row/cell audit downloads, immutable apply and undo.
- Custom placeholders, renaming, raw JSON mappings, invalid-conversion permission and column removal are under Advanced options.
- Reusable recipes remain supported; a name is generated if omitted. Preview automatically moves into view, including on narrow screens.

Live cases:

| Case | Observed result |
| --- | --- |
| Original `recipe_source`, select `-200` and replace missing with zero | 160 rows preserved; missing cells 1 → 0; exactly three audit entries: sentinel → missing, then two fills |
| Download preview audit, save recipe without typing a name, apply | Download completed, recipe appeared in saved choices, version 5 created |
| Convert `Date` with day/month/year dropdown | 160 conversions; 02/01/2024 correctly became 2024-01-02; version 6 created |
| Lowercase and merge `yes` into existing `no` using dropdowns | 80 changed cells; version 7 created; undo returned to its parent |
| Load new recipe against `workspace_fixture` | Valid preview, zero changes because its amount column was already cleaned; no extra version applied |
| Protect `label` then choose it for editing | Conversion and preview blocked |
| Preview replacing one missing feature, trimming and deduplication | One changed cell, no unrelated row removal |
| Responsive checks | No document horizontal overflow at 390px or normal 609px; desktop two-column layout and sticky preview checked at 1440px |

Mean/median model imputation remains fitted within training folds. This editor deliberately does not compute a whole-dataset imputation value and feed that learned statistic into holdout evaluation.

## All Machine Learning sections

| Section / internal view | Live checks and results |
| --- | --- |
| Train & Compare — leaderboard | Fresh random, grouped (`account_group`) and chronological (`date`) regression runs completed. Representative holdout R²: 0.9723, 0.9876 and 0.9860 respectively; results displayed simple baselines and residual plots. Fresh classification completed with macro F1 1.0000 on the deliberately simple synthetic fixture. Tuning/retained-baseline status displayed accurately. |
| Train & Compare — feature importance | Permutation importance chart rendered; encoded feature labels and non-causal interpretation were present. |
| Train & Compare — What-If | Classification and regression predictions completed. Invalid numeric text now rejects clearly; correcting it recovers. Blank fields use saved imputation with a visible notice. Old predictions are cleared when a new model is trained. |
| Feature Selection | Training-only assessment, eligibility flags, include/exclude checkboxes, 75% encoded selection and all-versus-selected CV comparison exercised. The selected-feature regression showed before/after CV values and selected encoded names. |
| Forecasting | Fresh two-series run completed with 8 windows and a 6-period horizon; both North/South views, model comparison, final holdout, interval coverage and error-by-horizon rendered. North MAE 11.65, South MAE 17.47. Measured coverage 83.3% was honestly warned about. |
| Forecasting — missing calendar period | Stop-on-gap returned a clear error; explicit forward-fill then completed with one missing period disclosed and imputed outcomes excluded from evaluation. |
| Text Classification | Fresh TF-IDF training on 5,572 SMS messages completed; macro F1 0.9568 vs baseline 0.4639. Per-class metrics, confusion matrix, precision–recall curves, reliability diagram and misclassified messages rendered. A new prize message was classified as spam. Positive-class and threshold controls responded. |
| Saved Runs | New runs persisted across navigation/project restore. Side-by-side comparison and saved settings/diagnostics worked; incompatible target/metric/split comparisons showed a warning. Model artifact download completed. |
| Batch Prediction | Missing columns rejected; invalid numeric values rejected; 15-row regression batch completed with missing-value handling, individual sensitivity explanation and CSV download. Four-message text batch with threshold 0.65 completed, retained request IDs and downloaded. Result previews identify the saved run and applied decision rule. |
| Poor-holdout warnings | Existing `chronological_shift` run displayed poor performance and distribution-shift warnings alongside its strongly negative holdout R². |

Synthetic scores test functionality, not expected performance on future real data. Forecast intervals are approximate, and classification probabilities remain explicitly uncalibrated estimates. Selecting thresholds on displayed holdout data is labeled exploratory.

## Bugs fixed during this audit

1. Stale What-If prediction and inputs survived replacing the trained model. New model jobs/results now clear them; late prediction responses from another run are rejected while ordinary page navigation still preserves the current result.
2. Restoring a project showed default target/task/split/feature settings alongside a different saved model. Controls now restore the saved configuration.
3. Forecast/text training kept displaying old results during replacement runs, including after failed attempts. Starting a new run clears them; text predictions also reset with the run.
4. What-If silently coerced invalid numeric strings into missing values. It now shares strict batch validation, rejects invalid/non-finite numeric strings and discloses legitimate imputation.
5. Custom numeric missing-value fills could introduce NaN/infinity; date fills could accept NaT; boolean fills lacked explicit validation. These inputs now validate.
6. Target protection did not cover renaming. Protected targets cannot be renamed.
7. Technical cleaning inputs were the default. Guided, bounded observed choices now cover ordinary cleanup; advanced syntax remains optional. Controls are locked during preview/apply so choices cannot change under an in-flight request.

## Automated verification and evidence

- Full backend suite before the final inference fix: **316 passed**.
- Focused inference/model regression after that fix: **65 passed**.
- Final full backend suite after the inference fix: **317 passed** in 337 seconds; see [backend-tests.txt](artifacts/ml-cleaning-audit/backend-tests.txt).
- Frontend state/API/chart suite: **21 passed**, including new model-prediction lifetime and restored-configuration regressions.
- Production build: successful; existing Plotly bundle-size warning remains.

Logs: [frontend tests](artifacts/ml-cleaning-audit/frontend-tests.txt), [production build](artifacts/ml-cleaning-audit/frontend-build.txt).

Screenshots: [guided controls](artifacts/ml-cleaning-audit/guided-cleaning.png), [before/after preview](artifacts/ml-cleaning-audit/cleaning-preview.png), [phone layout](artifacts/ml-cleaning-audit/cleaning-mobile.png).

The application is left running locally. This audit does not claim every possible dataset or future provider response is covered.

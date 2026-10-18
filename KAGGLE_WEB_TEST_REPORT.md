# Kaggle browser audit — 11 October 2026

Tested **10 real Kaggle files, containing 39,959 rows in total**, through the running React website at http://127.0.0.1:5173/. Files were selected with the browser's file chooser; analyses, chat requests, AutoML runs, predictions and downloads were initiated through the UI. Independent Pandas reads and read-only persisted-session checks corroborated the browser results. This was a CSV dataset audit, including multiple dialects and encodings, not a claim to test ten different file extensions.

## Dataset results

Every dataset completed the final analysis without recorded pipeline errors, generated charts, and downloaded a PDF and PowerPoint report. Browser chat returned the correct full-file row, column, duplicate and missing-cell counts for all ten datasets after fixes. Health scores describe the app's quality heuristic, not scientific validity or predictive usefulness.

| Dataset / source | Type | Rows × columns | Duplicate rows | Missing cells | Quality /100 | AutoML result |
|---|---|---:|---:|---:|---:|---|
| [Iris](https://www.kaggle.com/datasets/uciml/iris) | Multiclass botanical measurements with ordered row IDs | 150 × 6 | 0 | 0 | 97.5 | Logistic Regression; holdout macro F1 **1.0000** |
| [Red Wine Quality](https://www.kaggle.com/datasets/uciml/red-wine-quality-cortez-et-al-2009) | Numeric chemistry / ordinal outcome, tested as regression | 1,599 × 12 | 240 | 0 | 66.0 | Random Forest; holdout R² **0.5377** |
| [Titanic](https://www.kaggle.com/datasets/yasserh/titanic-dataset) | Mixed categories, text, missing values, binary label | 891 × 12 | 0 | 866 | 64.3 | LightGBM; holdout macro F1 **0.7568** |
| [Air Passengers](https://www.kaggle.com/datasets/rakannimer/air-passengers) | Monthly time series | 144 × 2 | 0 | 0 | 100.0 | Correctly rejects tabular AutoML: only date plus outcome |
| [Bank Churn](https://www.kaggle.com/datasets/shrutimechlearn/churn-modelling) | Customer records, identifiers, mixed features, binary label | 10,000 × 14 | 0 | 0 | 91.0 | CatBoost; holdout macro F1 **0.7694** |
| [Insurance](https://www.kaggle.com/datasets/mirichoi0218/insurance) | Numeric and categorical regression | 1,338 × 7 | 1 | 0 | 94.9 | LightGBM; holdout R² **0.8760** |
| [Air Quality](https://www.kaggle.com/datasets/fedesoriano/air-quality-data-set) | Sensor time series, semicolon delimiters, decimal commas, empty columns | 9,471 × 17 | 113 | 20,652 | 52.4 | Random Forest; raw-data holdout R² **0.7158** |
| [SMS Spam](https://www.kaggle.com/datasets/uciml/sms-spam-collection-dataset) | Free text, classification label, Windows encoding, sparse export columns | 5,572 × 5 | 403 | 16,648 | 33.0 | Correctly rejects tabular AutoML: no usable non-text features |
| [Superstore](https://www.kaggle.com/datasets/vivek468/superstore-dataset-final) | Retail transactions, dates, postal codes, skewed financial amounts, Windows encoding | 9,994 × 21 | 0 | 0 | 85.0 | Random Forest; holdout R² **0.0009**, weak generalization |
| [Pokémon](https://www.kaggle.com/datasets/abcsds/pokemon) | Catalog identifiers, categories, missing second types, Boolean label | 800 × 13 | 0 | 386 | 76.4 | Random Forest; holdout macro F1 **0.7297** |

The two rejected AutoML inputs are supported for profiling, analysis, chat and exports. The application does not currently train forecasting or natural-language models. All eight suitable tabular datasets completed model competitions without failed estimators, retained cross-validation selection rather than selecting on the holdout, and downloaded actual `.joblib` artifacts. Tuning was applied when validation improved; Bank Churn correctly retained its stronger baseline.

## Issues found and fixed

1. **Arbitrary identifiers polluted correlation analysis and measures.** Numeric-analysis selection now excludes row IDs, catalog `#` identifiers, postal codes, constant columns and empty columns. Schema and EDA use the same measurement selection. Postal codes and catalog numbers are excluded from automatic model features.
2. **A measure could also be used as its own comparison dimension.** Wine's `quality` column caused `cannot insert quality, already exists`, discarding visualizations. Diagnostic, hypothesis and chart selection now prevent self-comparison; the bar helper also guards this input.
3. **Text-only frequency charts failed.** Diagnostics computed a local `record_count`, but visualization tried to read it from the original SMS frame. Visualization recreates the frequency column locally without modifying the uploaded data.
4. **Dashboard and report quality scores disagreed.** The quality agent now uses the profiler's canonical score and status.
5. **Generated report statements contradicted computed results.** Executive summaries and published diagnostic briefings now use computed evidence. A skipped additive period decomposition no longer becomes a false claim that dates are absent. Unknown units, periods and causal explanations remain explicitly unestablished.
6. **Passenger counts were averaged as the main KPI.** `#Passengers` is recognized as an additive count: the 144-month total is **40,363 source units**. Non-additive metrics continue to use means.
7. **Sparse `Unnamed` export artifacts were suggested as targets.** These fields are excluded from target suggestions, alongside identifiers, constants and empty columns.
8. **Polling failed permanently after a transient connection failure.** Status/result polling now retries bounded transient network/server failures while preserving authorization errors and cancellation. Local development uses the configured Vite `/api` proxy; starting or completing analysis clears obsolete errors.
9. **AutoML could collide with a running analysis.** Training is visibly disabled until the dataset analysis finishes, with an explanatory status.
10. **Missing-value charts silently omitted columns after the first 15.** All affected columns are now shown with adaptive chart height; Air Quality visibly includes all 17.
11. **Basic chat counts depended on an LLM deciding to generate code.** Wine initially returned unknown counts. A standard four-count request now executes predefined isolated Pandas expressions and formats computed evidence without a provider call. The browser recheck returned **1,599 / 12 / 240 / 0**.

Expanded the bounded Kaggle downloader and real-file regressions from seven to ten sources, added focused regression cases for the findings, and updated development environment documentation. Kaggle denied the attempted diabetes sources; Pokémon was selected instead. Only the ten successfully downloaded sources above count toward this audit. Private API credentials are not included in the report or evidence files.

## Verification and evidence

- Final complete regression: **280 backend tests passed**, 130 warnings, zero failures; **15 frontend tests passed**, zero failures.
- Focused final published-output checks: **54 passed**, including all ten real files, analysis/report generation, targeted UI regressions, model checks and new diagnostic-text coverage.
- Production frontend build passed. Plotly still produces a nonfatal large-chunk warning.
- `pip check` and Python compilation passed.
- Reopened and parsed **10 actual downloaded PDFs and 10 PowerPoint files**, all with nonempty report content. Visually inspected the regenerated Air Quality PDF, including the corrected date/decomposition text.
- Browser prediction checks: Iris **Iris-setosa** for the entered measurement example; Insurance **6,000.04** for the entered synthetic example, including `children=0`. These are software checks, not decisions or advice.
- Restored saved analyses, chat and models through the UI after navigation and backend restarts. Rechecked desktop containment at 1280px and the normal 518px browser layout; reset the temporary viewport override.
- Initial full regression detected the SMS visualization failure. Final successful logs supersede earlier failure logs retained for traceability.

Evidence is under [`artifacts/kaggle-web-audit/`](artifacts/kaggle-web-audit/):

- [`source-truth.json`](artifacts/kaggle-web-audit/source-truth.json): independently computed file counts.
- [`verified-results.json`](artifacts/kaggle-web-audit/verified-results.json): final persisted results, charts, model scores, excluded features and tuning outcomes.
- [`verified-downloads.json`](artifacts/kaggle-web-audit/verified-downloads.json): the 20 final browser download paths, sizes and page/slide counts.
- [`regression-verified-final.txt`](artifacts/kaggle-web-audit/regression-verified-final.txt), [`frontend-build.txt`](artifacts/kaggle-web-audit/frontend-build.txt), and per-page browser text captures.
- [`web-final.jpg`](artifacts/kaggle-web-audit/web-final.jpg): final responsive web overview; dataset-specific screenshots and a rendered PDF page are also saved.

## Honest limits

**The tested application flows pass; the data and models are not uniformly good.** Superstore's final profit model has CV R² **0.8002** but holdout R² **0.0009**. It should not be treated as a validated prediction model. The holdout was not reused to select a different winner. Investigate extreme targets, split stability and data-generating conditions in a separate modeling exercise.

Air Quality retains repeated **-200** values and the original blank rows/columns. The shown missing counts count actual null cells; encoded sentinels require an explicit data-dictionary-based cleaning decision. Raw means and model scores therefore are not validated sensor conclusions. SMS's sparse export columns and duplicate messages explain its poor raw quality score. Wine's 240 duplicates require review before interpreting evaluation results as evidence of generalization to new observations.

Catalog structure, row IDs and arithmetic cannot establish scientific causes, currency, industry benchmarks, appropriate temporal validation or production model suitability. Some exploratory EDA/trend prose and analysis planning still use an LLM and should be reviewed alongside the computed evidence. This audit covers the ten files and exercised flows, not every possible dataset or deployment condition.

The React development app and local API were left running for manual testing.

# Workflow improvements and live validation

Validated 12 October 2026 in the running React application at
http://127.0.0.1:5173 with the authenticated backend at port 8000.

## Implemented

1. Guided Upload → Explore → Clean → Train → Evaluate → Predict → Report navigation,
   a persistent active-version header, and warnings for historical model results.
2. Saved cleaning recipes reusable across files: sentinel replacement, explicit
   missing-value replacement or row removal, date formats, category case/mapping,
   existing type/rename/duplicate operations, protected targets and immutable undo.
   Preview lists the first 100 changes; the complete proposed CSV audit is available
   before applying. Applied versions retain complete change audits.
3. Feature selection with training-partition ID/leakage flags, manual inclusion,
   automatic encoded-feature selection fitted inside cross-validation pipelines,
   and same-estimator before/after training-fold comparison.
4. Batch prediction for saved tabular and text models with strict column/numeric
   validation, extra-column preservation, preview and complete CSV download.
   An older-version model requires explicit acknowledgement in the interface.
5. Side-by-side saved-run comparison, per-row tabular feature sensitivity,
   per-class precision–recall curves, reliability diagrams, Brier scores,
   calibration error and adjustable binary thresholds.
6. Configurable rolling forecast windows, separate selection/calibration windows,
   an untouched final evaluation horizon, measured interval coverage, error by
   horizon and independent forecasts for multiple named series.

## Live browser results

| Check | Observed result |
| --- | --- |
| Version and stale-result workflow | Cleaning created version 4 of `workspace_fixture`; previous runs remained in history and were clearly flagged. New training used version 4. |
| Recipe save and reuse | Saved `Amount sentinel and fill` on one project and applied it to `recipe_source.csv`, a different 160-row file. Preview showed three changes: one sentinel replacement and two missing-value fills. |
| Full preview audit | Downloaded the three-change recipe audit and all 160 date conversions before applying. Downloads matched the displayed counts. |
| Date/category cleanup | `%d/%m/%Y` converted 2 January correctly rather than 1 February. Lowercase and explicit yes/no mappings produced another immutable version. History preserved original and all three derived versions. |
| Feature selection and training | Selected `feature`, `amount`, `segment`, retained 50% of encoded features and trained successfully. Saved selected features were the two segment encodings. |
| Before/after feature comparison | Same Logistic Regression estimator/folds: all-eligible macro-F1 0.9948; selected-feature macro-F1 1.0000. Holdout macro-F1 1.0000, baseline 0.3425, 192 training and 48 holdout rows. This deliberately simple fixture does not establish real-world generalization. |
| Classification threshold | Moving the positive-class threshold from 0.5 to 1 produced precision/recall/F1 of zero and a confusion matrix with 25 true negatives and 23 false negatives. |
| Calibration diagnostics | Fixture Brier score 0.0388 and calibration error 0.1966; probabilities explicitly labeled uncalibrated. |
| Individual explanation | Positive row sensitivity: replacing segment A with training mode B changed the positive probability from 0.7905 to 0.1848. Discarded numeric features had zero effect. |
| Invalid batch inputs | Missing required columns and invalid numeric values were rejected with specific messages. |
| Tabular batch | Predicted and downloaded all 15 rows; six yes and nine no predictions. Missing inputs used the saved preprocessing. |
| Older-version model | With an uploaded file, prediction remained disabled until the older-version acknowledgement was checked. |
| Run comparison | Two Logistic Regression runs displayed version, split, metric, holdout/CV scores, feature lists, selection percentage and baseline side by side, with cross-version cautions. |
| SMS classification | Retrained the 5,572-row SMS dataset; precision–recall and reliability diagnostics rendered. Spam average precision 0.974, Brier score 0.0330 and calibration error 0.1238. |
| Text batch | Four new messages predicted and downloaded, with request IDs retained: two ham and two spam. Threshold 1 changed all four decisions to ham without changing their probabilities. |
| Air Passengers forecast | Six backtest windows: three model-selection and three interval-calibration windows, followed by a separate 12-period final holdout. Exponential smoothing MAE 13.38 versus seasonal-naive 47.83. Coverage 83.3%; low-coverage warning visible. |
| Multiple series | North and South each forecast successfully from a 288-row fixture. MAE 13.38 and 20.07, coverage 83.3% for each. Switching series changed the charts and metrics. |
| Mobile layout | Prediction and cleaning pages had document width equal to viewport width at 320 pixels. Forecast and text batch pages also fit 390 pixels. Tables scroll inside their panels. Desktop checked at 1280 and 1440 pixels. |
| Persistence | Dataset versions and saved runs restored after backend restart. The local test login expired normally and was renewed; persisted models restored afterward. |

## Errors corrected during this work

- Perfectly predictive categorical features can produce infinite ANOVA scores.
  Percentile selection then removed every encoded feature. Selection now retains
  a deterministic, nonempty number of ranked features with `SelectKBest`.
- Reliability-bin floating-point boundaries could count a probability in adjacent
  bins. Each row now receives exactly one bin, including probability 1.
- Original/legacy versions without recorded audits now disable audit download
  instead of offering a link that returns an error.
- Complete preview audits can be downloaded before applying large recipes.

## Automated verification

- Backend: **297 passed**, 131 dependency/statistical warnings, no failures.
  [Final output](artifacts/workflow-audit/backend-final.txt).
- Frontend: **19 passed**.
- Production frontend build: **passed**. The existing Plotly bundle still produces
  a bundle-size advisory; there is no build error.
- Eight dedicated workflow tests cover recipe ownership/audits, fold-only feature
  selection, perfect categorical scores, ID/target-copy flags, inference validation,
  probability boundaries, threshold metrics, batch ownership/download/explanations,
  separate forecast calibration and partial failures across multiple series.
- A forecast regression test changes only final-holdout outcomes and verifies that
  model choice and interval widths do not change.

## Evidence and practical limits

- [Experiment comparison screenshot](artifacts/workflow-audit/run-comparison-live.png)
- [Version history screenshot](artifacts/workflow-audit/versions-live.png)
- [Multiple-series screenshot](artifacts/workflow-audit/multiseries-live.png)
- [Mobile prediction screenshot](artifacts/workflow-audit/batch-320.png)
- [Recipe preview audit](artifacts/workflow-audit/recipe-preview.csv)
- [Date preview audit](artifacts/workflow-audit/date-preview.csv)
- [Tabular predictions](artifacts/workflow-audit/tabular-predictions.csv)
- [Text predictions](artifacts/workflow-audit/text-predictions.csv)

Probability diagnostics measure reliability; they do not fit a calibration model.
Threshold exploration reuses holdout data and is not an independent performance
estimate. Individual explanations are one-feature sensitivity checks, not additive
SHAP values or causal effects. Older models need retraining for newly saved
diagnostics/reference values. Forecast bands remain approximate, and independent
series are not hierarchically reconciled. Low observed coverage is disclosed.
Manual feature decisions still require domain knowledge; leakage flags are hints.

Limits include 10,000 batch rows, 20 saved batches per project, 30 cleaning recipes
per user, 20 named forecast series, and the existing upload/version/storage quotas.
The application remains running for further manual testing.

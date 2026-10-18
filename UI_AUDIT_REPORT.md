# UI and analysis-output audit — 11 October 2026

The supplied screens were not ready for a polished release. This audit addressed
the observed layout and output failures, rebuilt the React workspace with light
and dark frosted materials, and exercised the running application in the browser.
Passing these checks does not establish that every possible dataset or AI answer
will be correct.

## Review of the ten attached screenshots

| Screens | Observed problem | Implemented correction |
| --- | --- | --- |
| 1, 5 | Raw Markdown and totals for rates, scores and other non-additive measures; unsupported business interpretation | Safe Markdown rendering, explicit aggregation labels, conservative mean/sum selection, computed KPI briefing, guarded report commentary |
| 2 | Clipped page heading, unstyled controls, misplaced model summary and download action | Correct scroll ownership, styled AutoML controls and summary grid, responsive tables, authenticated download button |
| 3, 9, 10 | Repeated dense EDA view with tiny labels | Shared chart theme, responsive chart sizing, readable axes and individual-column box plots |
| 4 | Crowded gauge, fixed 0–100 missingness scale, outliers described as confirmed errors | Accessible semicircle gauge, adaptive missingness scale, separate IQR/Z-score/agreement counts and review wording |
| 6 | Flat dark upload page without the requested glass appearance | Light frosted cards, atmospheric background, dark appearance option, hover/focus states, responsive navigation and saved-project restoration |
| 7, 8 | Failed calculation labeled as calculated evidence; speculative response | Supported bounded analytical methods, one repair attempt, explicit success/failure states, failed calculation excluded from factual evidence |

Screens 3/9/10 and 7/8 are duplicates; all ten attachments were considered.

## Additional failures found and fixed

- Numeric `experience_years` could become a fake timestamp and produce a false
  trend. Date selection now requires calendar evidence; time-series analysis
  requires at least two observed months. Non-additive monthly measures use means.
- Non-additive measures no longer receive revenue-style Pareto/concentration
  conclusions. Unknown currency and reporting periods are stated explicitly.
- Quality outlier checks silently stopped after eight numeric columns. They now
  cover all numeric columns, and the briefing does not add per-column flags to
  claim a unique affected-row count.
- Very small hypothesis-test probabilities could display as zero and useful
  fields were omitted. The table now displays raw and Holm-adjusted probabilities,
  conclusions and assumptions explicitly, using scientific notation when needed.
- Feature-importance text incorrectly described importance as a percentage of
  model decisions. It now states the actual method and limits interpretation to
  the displayed importance scores, without causal claims.
- A temporary authentication fetch failure could clear the login. Network
  interruptions now offer retry; unauthorized responses still clear credentials.
- SQLite context managers committed transactions without closing connections,
  causing Windows cleanup failures. Explicit connection closing fixes this.
- Switching datasets clears unrelated analysis/model/chat state. Saved projects
  restore their own results and conversations through the application interface.

## Browser verification

Tested the running React application against the local backend, using a dedicated
test account and a real CSV upload containing 2,000 rows and 13 numeric columns.

| Workflow | Observed result |
| --- | --- |
| Authentication | Sign-in feedback, password visibility and workspace loading exercised; transient connection retry recovered the workspace |
| Upload and sample | Actual CSV file chooser upload; SaaS sample profiled all 600 rows and eight columns |
| Analysis | Completed the real queued pipeline and regenerated results after the final quality/KPI fixes |
| Quality | 89.7 score, 60 missing cells (0.23%), zero duplicate rows, eight review issues; all 13 numeric columns checked |
| Chat | Actual calculation succeeded: zero duplicate rows; top absolute target correlations income 0.6128, performance_score 0.4251, experience_years 0.3090; target self-correlation excluded |
| AutoML | Six models evaluated; Ridge winner, CV R² 0.6824 ± 0.032, holdout R² 0.7019; ten Optuna trials applied |
| Model tools | Authenticated model download, permutation importance and a twelve-feature what-if request succeeded |
| Reports | PDF and PowerPoint buttons downloaded nonempty files; PDF first page rendered and inspected, PowerPoint parsed as seven slides |
| State | Page navigation retained model/chat; a new sample cleared unrelated results; reopening the saved CSV restored them; backend restart preserved the saved session |
| Interaction | Page search, sidebar collapse, mobile menu and focus handling, theme switching, box-plot selection and report navigation exercised |
| Responsive layout | Desktop, 768-pixel tablet and 390 × 844 phone checks; corrected report overflow; phone overview/chat/AutoML retained horizontal containment |

The saved live test project is `09e13cf7-1f7e-4700-ac0f-0f70ea09bab8`.
Final regenerated analysis job: `2b8dfa8c-60c4-49f7-a7de-b58022dc57fa`.

## Automated validation

- **263 Python tests passed**, with 110 nonfatal dependency/numerical warnings.
  Full output: [python-regression.txt](artifacts/ui-audit/python-regression.txt).
- **14 frontend Node tests passed**, including state restoration, Markdown safety,
  calculation status and probability formatting.
- Production frontend build passed; Python compilation passed; `pip check`
  reported no broken requirements.
- Added regression coverage for non-additive metrics, unsupported narrative claims,
  date inference, bounded chat repair/failure behavior, exported reports and
  quality checks beyond eight numeric columns.

Earlier file-format and downloaded-source coverage is documented separately in
[APPLICATION_TEST_REPORT.md](APPLICATION_TEST_REPORT.md). It is not a claim that
all those sources were manually retested in the browser during this UI audit.

## Visual evidence

- [Desktop quality](artifacts/ui-audit/quality-desktop.jpg)
- [Desktop upload](artifacts/ui-audit/upload-desktop.jpg)
- [Phone upload](artifacts/ui-audit/upload-phone.jpg)
- [Desktop AutoML](artifacts/ui-audit/automl-desktop.jpg)
- [Desktop box plot](artifacts/ui-audit/box-plot-desktop.jpg)
- [Rendered PDF first page](artifacts/ui-audit/report-page1.png) — inspected during
  the audit before the final KPI/quality regeneration.

The final regenerated PDF was also parsed successfully: two pages, nonempty
content, the updated 89.7 quality score and explicit unknown units.

## Remaining limits

- Generated commentary still requires review. The claim checks catch selected
  unsupported patterns; they are not a general factuality guarantee.
- Metric-name heuristics are conservative defaults. Reliable business benchmarks
  and currency/period interpretation require an explicit metric dictionary.
- The Plotly production chunk remains large (about 4.68 MB before compression),
  generating a build warning. Analysis pages are lazy loaded.
- PowerPoint downloads were structurally checked; desktop PowerPoint visual
  rendering was not tested. Browser visual checks covered the React application,
  not every browser/OS combination or every Streamlit interaction.
- Numerical precision warnings remain for deliberately degenerate statistical
  test fixtures; no regression test failed.

Local app: http://127.0.0.1:5173/ (backend: http://127.0.0.1:8000/).

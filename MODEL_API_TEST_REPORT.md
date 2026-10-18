# Live API key and model routing audit

Validated 18 October 2026. Tests used only synthetic prompts/data. Secret values
were neither printed nor stored in the audit. This is a small task-specific check,
not a universal model ranking, capacity/load test or guarantee of future accuracy.

## Credential readiness

All **24 configured keys** returned a successful synthetic readiness response:
6 Gemini, 11 Groq and 7 NVIDIA. Four initially failed requests recovered on a
separate recheck. Gemini 503 overload responses and a Groq connection timeout
were not incorrectly classified as invalid credentials. Each key was tested
against a readiness model, not every possible key/model combination.

| Provider | Key variable | First check | Successful readiness model | Successful request seconds |
| --- | --- | --- | --- | --- |
| gemini | `Gemini_ApiKey_1` | Passed | `gemini-3.5-flash-lite` | 16.63 |
| gemini | `Gemini_ApiKey_2` | HTTP 503 | `gemini-3.8-flash` | 4.81 |
| gemini | `Gemini_ApiKey_3` | Passed | `gemini-3.5-flash-lite` | 7.42 |
| gemini | `Gemini_ApiKey_4` | HTTP 503 | `gemini-3.8-flash` | 12.52 |
| gemini | `Gemini_ApiKey_5` | Passed | `gemini-3.5-flash-lite` | 8.11 |
| gemini | `Gemini_ApiKey_6` | HTTP 503 | `gemini-3.8-flash` | 3.87 |
| groq | `GROQ_API_KEY_1` | Passed | `openai/gpt-oss-120b` | 1.22 |
| groq | `GROQ_API_KEY_2` | Passed | `openai/gpt-oss-120b` | 11.09 |
| groq | `GROQ_API_KEY_3` | Passed | `openai/gpt-oss-120b` | 1.22 |
| groq | `GROQ_API_KEY_4` | Passed | `openai/gpt-oss-120b` | 1.10 |
| groq | `GROQ_API_KEY_5` | Passed | `openai/gpt-oss-120b` | 1.14 |
| groq | `GROQ_API_KEY_6` | Passed | `openai/gpt-oss-120b` | 0.88 |
| groq | `GROQ_API_KEY_7` | Passed | `openai/gpt-oss-120b` | 11.03 |
| groq | `GROQ_API_KEY_8` | Passed | `openai/gpt-oss-120b` | 1.09 |
| groq | `GROQ_API_KEY_9` | Passed | `openai/gpt-oss-120b` | 1.17 |
| groq | `GROQ_API_KEY_10` | Passed | `openai/gpt-oss-120b` | 13.02 |
| groq | `GROQ_API_KEY_11` | ConnectTimeout | `openai/gpt-oss-120b` | 1.13 |
| nvidia | `NVIDIA_API_KEY_1` | Passed | `openai/gpt-oss-20b` | 5.14 |
| nvidia | `NVIDIA_API_KEY_2` | Passed | `openai/gpt-oss-20b` | 12.70 |
| nvidia | `NVIDIA_API_KEY_3` | Passed | `openai/gpt-oss-20b` | 1.82 |
| nvidia | `NVIDIA_API_KEY_4` | Passed | `openai/gpt-oss-20b` | 4.00 |
| nvidia | `NVIDIA_API_KEY_5` | Passed | `openai/gpt-oss-20b` | 2.54 |
| nvidia | `NVIDIA_API_KEY_6` | Passed | `openai/gpt-oss-20b` | 1.46 |
| nvidia | `NVIDIA_API_KEY_7` | Passed | `openai/gpt-oss-20b` | 2.27 |

## Initial model tasks

Each of the eight selected models received the same five short tasks, without
hidden fallback: ordered plan, exact schema roles, numerical/statistical
interpretation, constrained chat code executed in the existing subprocess, and
structured forecast/probability synthesis. Pass checks use explicit expected
values. The synthesis check validates supplied numeric/boolean fields and basic
summary structure; it is not a comprehensive test of report-writing quality.

| Provider / model | Plan | Schema | Interpretation | Safe chat code | Synthesis | Passed | Median successful check |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemini / `gemini-3.5-flash-lite` | Pass | HTTP 503 | Pass | Pass | Pass | 4/5 | 6.94s |
| gemini / `gemini-3.8-flash` | Pass | Pass | Pass | HTTP 503 | Pass | 4/5 | 5.59s |
| groq / `openai/gpt-oss-120b` | Pass | Pass | Wrong output | Pass | Pass | 4/5 | 9.87s |
| nvidia / `z-ai/glm-5.3-flash` | Timeout | Timeout | Timeout | Timeout | Timeout | 0/5 | No successful task |
| nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | Pass | Pass | Pass | Pass | Pass | 5/5 | 1.93s |
| nvidia / `stepfun-ai/step-5-preview` | Pass | Pass | Pass | Pass | Pass | 5/5 | 18.26s |
| nvidia / `google/diffusiongemma-26b-a4b-it` | Wrong output | Pass | Wrong output | Pass | Pass | 3/5 | 2.00s |
| nvidia / `openai/gpt-oss-20b` | Timeout | Pass | Pass | Pass | Pass | 4/5 | 7.98s |

Important findings and routing changes:

- NVIDIA Nemotron **3.5 Super VL 120B A12B** passed all five first-round checks.
  This is the exact new model ID supplied by the owner, not the older Nemotron 3
  environment default. It became primary for schema, EDA, hypotheses and chat.
- GLM 5.3 Flash timed out on all five non-streaming tasks. A separate streaming
  readiness call also timed out (20.68 seconds). It is excluded for now; this
  does not prove the endpoint can never work.
- DiffusionGemma added a forbidden extra dimension to the requested plan and
  incorrectly described a p-value as the probability the null hypothesis is true.
  It is excluded from active routing.
- Groq GPT-OSS 120B made the same p-value mistake. It remains useful for the
  passing supervisor/code/schema/synthesis checks, but is absent from hypothesis
  routes. Only Groq GPT-OSS **120B** is routed; Groq 20B/Qwen were removed.
- Flash-Lite passed the initial interpretation case, then made the p-value mistake
  on a repeat through the integrated route. That failed route validation is
  preserved. EDA and hypotheses now use Nemotron, Gemini 3.8 and Step 5 instead.
  Flash-Lite remains on computed trend commentary and supervisor/schema fallback.
- Step 5 passed all five checks, but was slower in this sample. It is a statistical
  interpretation fallback. NVIDIA GPT-OSS 20B passed four checks with one initial
  connection timeout and remains a chat-expression fallback.
- Gemini 3.8 passed four initial checks with one overload response. It succeeded
  on later comparison and interpretation fallbacks; it is active in those roles.

## Final active routes

Routing configuration: [backend/model_routes.json](backend/model_routes.json).
Explicit tasks override the legacy default-provider preference. Unused old model
settings in a private environment file do not override this routing table.

| Task | First provider/model | Fallbacks in order |
| --- | --- | --- |
| supervisor | groq / `openai/gpt-oss-120b` | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` → gemini / `gemini-3.5-flash-lite` |
| schema | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | gemini / `gemini-3.5-flash-lite` → groq / `openai/gpt-oss-120b` |
| eda | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | gemini / `gemini-3.8-flash` → nvidia / `stepfun-ai/step-5-preview` |
| hypothesis | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | gemini / `gemini-3.8-flash` → nvidia / `stepfun-ai/step-5-preview` |
| trend | gemini / `gemini-3.5-flash-lite` | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` → groq / `openai/gpt-oss-120b` |
| chat_code | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | groq / `openai/gpt-oss-120b` → nvidia / `openai/gpt-oss-20b` |
| chat_answer | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | gemini / `gemini-3.8-flash` → groq / `openai/gpt-oss-120b` |
| comparison | gemini / `gemini-3.8-flash` | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` → groq / `openai/gpt-oss-120b` |

Local cleaning, profiling, fitting, metrics, constrained execution, charts and
PDF/PPTX export remain deterministic/local. This change does not introduce LLM
calls into the deliberately deterministic quality/KPI/diagnostic/report stages.

## Live validation of the application service

After the Flash-Lite finding was corrected, **all eight configured task routes
passed** the synthetic application-service checks. Real NVIDIA HTTP 500 and
connection failures switched to Gemini 3.8 and returned correct answers. This
was actual failover, not a mocked success. Network/overload delays still exist;
measured end-to-end checks ranged from 1.00 to 49.38 seconds in that run.

The running authenticated API was also tested with a new synthetic 60-row CSV.
Its complete analysis job finished with **no pipeline errors**. Analytical chat
used the constrained subprocess successfully and returned the exact revenue totals:
**East 5,070; West 5,400**. The API's shared health counters recorded successful
requests on all three platforms: Groq 1, NVIDIA 5, Gemini 1.

## Concurrency, limits and failure handling

- Three independently monitored provider pools now include all six Gemini keys.
- Runtime reservation allows one in-flight request per key; other account keys
  can serve concurrent work. The live audit itself used bounded thread pools.
- Conservative per-key configured RPM ceilings: NVIDIA 40, Groq 30,
  Gemini Flash-Lite 15, Gemini reasoning 5. These are configuration, not verified
  account entitlement or a guarantee that the provider cannot rate-limit.
- Groq additionally reserves estimated input plus maximum output against an
  8,000-token/minute budget. Estimation is not exact tokenization/billing.
- 429/auth failures can try another available owned-account key within the
  bounded retry budget. Rate-limit cooldowns respect numeric Retry-After values.
- Bad/unknown models, malformed/incomplete final answers, overload and transport
  errors switch to the next model instead of exhausting every key on one outage.
- Structured schema/plan outputs must be JSON objects before the agent validates
  their columns/roles/plan. The chat interpreter and resource limits remain intact.
- Key health reads contact no providers. Counters and reservations are process-local;
  separate API/Streamlit processes have independent counters. Use one API worker.

## Verification and evidence

- [Initial key checks](artifacts/model-audit/keys.json)
- [Transient-failure key rechecks](artifacts/model-audit/recheck.json)
- [Forty direct task checks](artifacts/model-audit/tasks.json)
- [GLM streaming readiness attempt](artifacts/model-audit/glm-stream.json)
- [Initial integrated checks, including the wrong Flash-Lite answer](artifacts/model-audit/live-routes-initial.json)
- [Final eight passing live task routes](artifacts/model-audit/live-routes.json)
- [Authenticated API analysis, chat and public health summary](artifacts/model-audit/api-live.json)
- [Regression output](artifacts/model-audit/regression-final.txt)

New regression coverage checks Gemini health accounting, provider ordering,
model-level failure switching, rejected empty/truncated/invalid JSON responses,
parallel account reservations, RPM/token budgets, Retry-After cooldowns and
exclusion of failed model candidates. The focused suite passed **78 tests**.
The full regression suite passed **307 tests** (131 dependency/statistical warnings,
no failures). The final output is linked above.

The app is running at http://127.0.0.1:5173 with backend port 8000.
Provider availability can change; passing a few fixtures does not remove the
need for domain review or make model commentary a proof of correctness.

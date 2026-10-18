# Model list and evaluation register

Created: 18 October 2026. Updated: 18 October 2026.

This catalog now includes live results and activated task routing. All 24 configured
keys completed a synthetic readiness request, including rechecks after transient
errors. Eight selected models received five task checks each. The final eight
application routes passed live synthetic validation, including real failover.

See [MODEL_API_TEST_REPORT.md](MODEL_API_TEST_REPORT.md) for failures, measured
latencies and limitations. [backend/model_routes.json](backend/model_routes.json)
is the active task-routing configuration. The original allocation in section 3
is retained as a proposal; the measured routes below supersede it.

| Active task | First model | Fallbacks in order |
| --- | --- | --- |
| supervisor | groq / `openai/gpt-oss-120b` | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` → gemini / `gemini-3.5-flash-lite` |
| schema | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | gemini / `gemini-3.5-flash-lite` → groq / `openai/gpt-oss-120b` |
| eda | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | gemini / `gemini-3.8-flash` → nvidia / `stepfun-ai/step-5-preview` |
| hypothesis | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | gemini / `gemini-3.8-flash` → nvidia / `stepfun-ai/step-5-preview` |
| trend | gemini / `gemini-3.5-flash-lite` | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` → groq / `openai/gpt-oss-120b` |
| chat_code | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | groq / `openai/gpt-oss-120b` → nvidia / `openai/gpt-oss-20b` |
| chat_answer | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` | gemini / `gemini-3.8-flash` → groq / `openai/gpt-oss-120b` |
| comparison | gemini / `gemini-3.8-flash` | nvidia / `nvidia/nemotron-3.5-super-vl-120b-a12b` → groq / `openai/gpt-oss-120b` |

## 1. Key pools found in the project

Only variable names are recorded. Never paste actual API keys in this document.

| Provider | Environment variables | Present in `.env` | Current application integration |
| --- | --- | --- | --- |
| Google Gemini | `Gemini_ApiKey_1` through `Gemini_ApiKey_6` | 6 nonempty variables | Integrated; primary trend route and reasoning/comparison fallbacks |
| Groq | `GROQ_API_KEY_1` through `GROQ_API_KEY_11` | 11 nonempty variables | Integrated; primary supervisor route; only GPT-OSS 120B is routed |
| NVIDIA NIM | `NVIDIA_API_KEY_1` through `NVIDIA_API_KEY_7` | 7 nonempty variables | Integrated; Nemotron 3.5 Super VL is primary for schema, EDA, hypothesis and chat |

The owner reports that the keys belong to separate accounts. Presence in `.env`
alone does not establish billing status, account/project independence or remaining
quota. All three key pools now participate in requests and health monitoring.
Successful readiness calls are recorded per key alias in the test report.

## 2. Selected candidates for the data-science workflow

Groq has **only GPT-OSS 120B** in this requested candidate list. GPT-OSS 20B below
is an **NVIDIA-hosted** candidate because it was explicitly supplied for NVIDIA.
Groq 20B/Qwen were removed from the active routing candidates. Older environment
model variables may remain; the task-routing JSON is authoritative.

The role suggestions below precede testing; the active routing table above is
authoritative. These small checks do not establish universal winners. Public model
documentation and a user-provided example are distinct from a successful request
using this project's credentials.

| Provider | Model | Exact API model ID | Proposed tasks to evaluate | Evidence / test status |
| --- | --- | --- | --- | --- |
| Gemini | Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | Supervisor plans; schema semantics; concise computed-evidence explanations; straightforward chat expressions; chart captions; report drafts | 4/5 initial task checks passed; measured failures and active decisions are recorded below |
| Gemini | Gemini 3.8 Flash | `gemini-3.8-flash` | Complex diagnostic/hypothesis interpretation; difficult chat expressions; cross-agent synthesis; final report review | 4/5 initial task checks passed; measured failures and active decisions are recorded below |
| Groq | OpenAI GPT-OSS 120B | `openai/gpt-oss-120b` | Planning; difficult interpretation; analytical chat answers; report synthesis | 4/5 initial task checks passed; measured failures and active decisions are recorded below |
| NVIDIA | GLM 5.3 Flash | `z-ai/glm-5.3-flash` | Structured schema/plan output; code-expression generation; short interpretation | 0/5 initial task checks passed; measured failures and active decisions are recorded below |
| NVIDIA | Nemotron 3.5 Super VL 120B A12B | `nvidia/nemotron-3.5-super-vl-120b-a12b` | Complex interpretation/synthesis; optional chart-image interpretation after an actual image-input test | 5/5 initial task checks passed; measured failures and active decisions are recorded below |
| NVIDIA | Step 5 Preview | `stepfun-ai/step-5-preview` | Planning; statistical interpretation; supported expression generation; optional structured tool-call tests | 5/5 initial task checks passed; measured failures and active decisions are recorded below |
| NVIDIA | DiffusionGemma 26B A4B IT | `google/diffusiongemma-26b-a4b-it` | Hypothesis/diagnostic interpretation; reasoning and report synthesis; supported expressions | 3/5 initial task checks passed; measured failures and active decisions are recorded below |
| NVIDIA | OpenAI GPT-OSS 20B | `openai/gpt-oss-20b` | Schema extraction; simple plans; concise summaries; straightforward chat expressions | 4/5 initial task checks passed; measured failures and active decisions are recorded below |

The new NVIDIA Nemotron ID contains **`3.5-super-vl`**. It is different from the
older environment default, `nvidia/nemotron-3-super-120b-a12b`.
The active task routes explicitly use the newly tested 3.5 Super VL model.

## 3. Original proposed workflow allocation supplied by the owner

This preserves the suggested Gemini allocation as a starting hypothesis. NVIDIA
and Groq candidates should receive the same tasks before selecting primary and
fallback routes. The tested active routes at the top supersede this original proposal.

| Workflow | Proposed starting path | Model responsibility | Application responsibility |
| --- | --- | --- | --- |
| Loader and numerical profiling | Existing Python | Optional explanation only | Parse complete files; infer/validate types; compute profiles locally |
| Supervisor | Gemini 3.5 Flash-Lite | Interpret the objective; propose a structured analysis plan | Validate agent names, columns and ordering/dependencies |
| Schema agent | Gemini 3.5 Flash-Lite | Suggest business meaning and semantic roles | Validate types, roles and real column references |
| Quality, KPI and EDA | Gemini 3.5 Flash-Lite | Explain supplied missingness, distributions, associations, outliers and KPIs | Compute all values; preserve units and correct aggregations |
| Diagnostic and hypothesis | Gemini 3.8 Flash for complex interpretation | Explain combined evidence, assumptions, statistical uncertainty and limitations | Compute tests/decompositions and check evidence-grounded claims |
| Trend agent | Gemini 3.5 Flash-Lite | Explain supplied period aggregates, Mann–Kendall/STL results and forecast diagnostics | Compute time-based statistics and backtests |
| Visualization | Gemini 3.5 Flash-Lite | Suggest supported specifications, titles and captions | Validate chart schemas; render charts from actual data |
| Analytical chat | Gemini 3.5 Flash-Lite; 3.8 Flash for harder expressions | Generate only the interpreter's supported analytical expressions and explain returned evidence | Enforce interpreter policy, subprocess isolation, time/memory limits and evidence checks |
| Report | Gemini 3.5 Flash-Lite draft; optional 3.8 Flash synthesis | Write/edit commentary grounded in supplied results | Validate claims; create PDF and PowerPoint artifacts locally |
| AutoML, forecasting, text classification and prediction | Existing training/inference code | Explain results and limitations | Fit models; perform fold-specific preprocessing/selection; backtest; predict; compute metrics locally |

This is **proposed behavior**, not a claim that every current agent calls an LLM.
Some current quality/KPI/diagnostic/report content is deliberately deterministic.
Do not replace validated local computations with model-generated numbers.

## 4. Other Gemini text candidates visible in the screenshots

Retained so the supplied inventory is complete, without automatically including
every model in the first benchmark. Only the selected 3.5 Flash-Lite and 3.8 Flash have task results; the other models
in this inventory were not benchmarked.
Limits are transcribed from the owner's screenshots dated 17 October 2026; they
are not live quota checks and must not be multiplied by six.

| Screenshot name | API ID / identification status | Shown RPM limit | Shown TPM limit | Candidate use / note |
| --- | --- | --- | --- | --- |
| Gemini 2 Flash | `gemini-2.0-flash` | 0 | 0 | Legacy; official catalog marks shut down |
| Gemini 2 Flash Lite | `gemini-2.0-flash-lite` | 0 | 0 | Legacy; official catalog marks shut down |
| Gemini 2.5 Flash | `gemini-2.5-flash` | 5 | 250K | Optional legacy comparison; account access needs checking |
| Gemini 2.5 Flash Lite | `gemini-2.5-flash-lite` | 10 | 250K | Optional legacy comparison; account access needs checking |
| Gemini 2.5 Pro | `gemini-2.5-pro` | 0 | 0 | Not a first-round candidate with the shown quota |
| Gemini 3 Flash | `gemini-3-flash-preview` | 5 | 250K | Optional text-workflow comparison |
| Gemini 3.1 Pro | `gemini-3.1-pro-preview` | 0 | 0 | Not a first-round candidate with the shown quota |
| Gemini 3.1 Flash Lite | `gemini-3.1-flash-lite` | 15 | 250K | Optional concise/structured-output comparison |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 5 | 250K | Optional general interpretation comparison |
| Gemini 3.5 Flash Lite | `gemini-3.5-flash-lite` | 15 | 250K | Selected candidate above |
| Gemini 3.7 Flash | Exact callable ID still to verify | 5 | 250K | Preserve screenshot name; do not invent an API ID |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 5 | 250K | Selected candidate above |
| Gemini 4 Argon | `gemini-4-argon` | 0 | 0 | Not a first-round candidate with the shown quota |

Google's current catalog distinguishes legacy 2.5 access from newer models;
actual access still needs checking on each intended project. A screenshot entry
or positive quota is not proof that a completion succeeds.

## 5. Remaining Google models shown in the screenshots

These are preserved as an inventory, **not enabled for the current data-science
workflow**. Model names are transcribed from the supplied images. Unless an API
ID is explicitly given above, resolve it through the official provider catalog
and the authenticated model list before testing. No image, audio, video, agent,
embedding or robotics inference was performed in the text-workflow benchmark.

| Screenshot model/name | Category | Shown RPM limit | Shown TPM limit | Relevance / identification note |
| --- | --- | --- | --- | --- |
| Antigravity | Agent | 60 | 100K | Managed agent; separate workflow and execution model |
| Deep Research Pro Preview | Agent | 0 | 0 | Research, not the current local analysis pipeline; exact mapping needs checking |
| Computer Use Preview | Other | 0 | 0 | UI automation; exact version needs checking |
| Nano Banana (Gemini 2.5 Flash Preview Image) | Image | 0 | 0 | Optional image generation; not required for data charts |
| Gemini 2.5 Flash TTS | Speech generation | 3 | 10K | Optional spoken report narration |
| Gemini 2.5 Pro TTS | Speech generation | 0 | 0 | Optional spoken report narration |
| Nano Banana Pro (Gemini 3 Pro Image) | Image | 0 | 0 | Optional image generation |
| Nano Banana 2 (Gemini 3.1 Flash Image) | Image | 0 | 0 | Optional image generation |
| Nano Banana 2 Lite (Gemini 3.1 Flash Lite Image) | Image | 0 | 0 | Optional image generation |
| Gemini 3.1 Flash TTS | Speech generation | 3 | 10K | Optional spoken report narration |
| Gemini 3.5 Transcribe | Transcription | 3 | 10K | Optional audio-to-text input |
| Gemini 3.8 Flash Lite TTS | Speech generation | 3 | 10K | Optional spoken report narration |
| Gemini 3.8 Flash TTS | Speech generation | 3 | 10K | Optional spoken report narration |
| Gemini Embedding 1 | Embedding | 100 | 30K | Possible future semantic search; not a chat-completion model |
| Gemini Embedding 2 | Embedding | 100 | 30K | Possible future semantic search; not a chat-completion model |
| Gemini Nano Banana 2.1 | Image | 0 | 0 | Optional image generation |
| Gemini Omni 1.1 Flash | Generative media | 0 | 0 | Verify whether this and the next display name share an endpoint |
| Gemini Omni Flash | Generative media | 0 | 0 | Preserve separate screenshot entry until resolved |
| Gemini Robotics ER 2 Preview | Robotics | 5 | 250K | No current robotics workflow |
| Gemma 4 26B | Other | 30 | 16K | Google-hosted Gemma entry; exact callable ID/access to verify |
| Gemma 4 31B | Other | 30 | 16K | Google-hosted Gemma entry; exact callable ID/access to verify |
| Lyria 3 Clip | Music | 0 | 0 | No current music workflow |
| Lyria 3 Pro | Music | 0 | 0 | No current music workflow |
| Veo 3 Fast Generate | Video | 0 | Not shown | No current video-generation workflow |
| Veo 3 Generate | Video | 0 | Not shown | No current video-generation workflow |
| Veo 3 Lite Generate | Video | 0 | Not shown | No current video-generation workflow |
| Gemini 2.5 Flash Native Audio Dialog | Live API | Unlimited | 1M | Future voice interaction; separate live protocol |
| Gemini 3 Flash Live | Live API | Unlimited | 65K | Exact display-name/version mapping to verify |
| Gemini 3.5 Live Translate | Live API | Unlimited | 20K | Future live translation |
| Gemini 3.5 Transcribe Live | Live API | Unlimited | 20K | Future live transcription |
| Gemini 3.8 Live | Live API | Unlimited | 65K | Future voice interaction |
| Gemini 3.8 Live Extended Thinking | Live API | Unlimited | 65K | Future voice interaction with reasoning |

Screenshot rows under **Tools → Map grounding** are tool capability entries,
not additional independently selected language models. Duplicated model rows
across screenshots have been deduplicated here. The application screenshot
documents the UI; it is not model-availability or benchmark evidence.

## 6. Supplied NVIDIA invocation details

Base URL: `https://integrate.api.nvidia.com/v1`.
Chat endpoint: `POST /chat/completions`.
The examples use OpenAI-compatible or `ChatNVIDIA` clients; that does not mean
the calls use OpenAI's API or require an OpenAI API key.

| Exact model ID | Settings in the supplied example | What still needs validation |
| --- | --- | --- |
| `z-ai/glm-5.3-flash` | temperature 0.5; top_p 1; max_tokens 1024; streaming | Endpoint access; output completeness; structured output; evidence grounding |
| `nvidia/nemotron-3.5-super-vl-120b-a12b` | temperature 1; top_p 0.95; max_completion_tokens 16384; seed 42; enable_thinking true; parallel_tool_calls true | Parameter compatibility; time/token budget; actual image input; actual tool calls |
| `stepfun-ai/step-5-preview` | temperature 0.5; top_p 1; max_completion_tokens 4096; streaming; tool definitions | Task-specific tools and schema adherence; remove the unrelated character/color demo tools from analytics tests |
| `google/diffusiongemma-26b-a4b-it` | temperature 1; top_p 0.95; max_completion_tokens 4096; enable_thinking true | Thinking-parameter support; final answer versus reasoning text; latency and grounding |
| `openai/gpt-oss-20b` | temperature 1; top_p 1; max_tokens 4096; streaming | Structured output; interpreter-compatible expressions; evidence grounding |

`$NVIDIA_API_KEY` inside a Python string is a placeholder, not automatic shell
environment expansion. A future harness should load a selected configured key
server-side without printing it. Preserve the difference between `max_tokens`
and `max_completion_tokens`, and between standard fields and provider-specific
`chat_template_kwargs`; test parameter support rather than forwarding every
example option to every endpoint.

## 7. Groq quota recorded from the supplied screenshot

| Selected model | RPM | Requests/day | TPM | Tokens/day | Evidence |
| --- | --- | --- | --- | --- | --- |
| `openai/gpt-oss-120b` | 30 | 1,000 | 8,000 | 200,000 | Organization-limits screenshot dated 17 October 2026; not a live check |

The screenshot describes the displayed organization/project context. Eleven keys
must not be interpreted as eleven times this capacity without independently
checking the applicable accounts, projects, limits and provider rules. Respect
429 responses and backoff; do not use pool rotation to evade provider limits.

## 8. Required tests before assigning a primary task

Use synthetic fixtures and fixed expected results, not private uploaded datasets.
Record provider, exact model, key **alias only**, date, request settings, status,
latency and token usage. Evaluate the requested model directly: no hidden
cross-model fallback during a benchmark.

| Test | Required evidence / pass condition |
| --- | --- |
| Availability | Successful request with nonempty final content; distinguish authentication failure, model unavailable, quota/rate limit, timeout and unsupported parameters |
| Supervisor | Valid plan references real agents/columns; schema precedes quality and trend precedes dependent visualization |
| Schema | Valid structured output; correct numeric/date/category roles; flag likely IDs; no invented columns |
| Numerical interpretation | Use supplied computed values exactly; do not sum percentages or invent units, benchmarks or trends |
| Hypothesis/diagnostic | Correct p-value interpretation, assumptions, multiple-testing limits and association-versus-causality wording |
| Analytical chat | Generated expression passes the existing constrained interpreter and produces the fixture's expected result within subprocess limits |
| Matplotlib code example | Optional developer-code test: inspect/parse generated code separately; passing this does not prove compatibility with the app's constrained analytical interpreter |
| Visualization | Supported chart specification; correct axes/units and actual data fields; application renders it |
| Report | Evidence-grounded synthesis; no fabricated causes/actions stated as proven facts; local PDF/PPTX remains authoritative |
| Multimodal | Send a known synthetic chart/image and check observable content; a model's answer to “are you multimodal?” is not a capability test |
| Streaming/thinking/tools | Capture final content separately from reasoning; validate actual tool name/arguments; never execute arbitrary returned tools/code |
| Reliability and speed | Repeat representative tasks and record failures/truncation, median/tail latency and token usage; one successful demo does not establish a winner |

Live readiness and task benchmarks have now been run. See the test report and raw
JSON artifacts. Model documentation alone is not proof of inference availability.

## 9. Results ledger

First-round results below include outages and wrong answers. Live routing checks
then exposed a repeated p-value mistake from Flash-Lite; it was removed from
EDA/hypothesis interpretation routes. These are small synthetic checks, not a
comprehensive model ranking. Multimodal, tool-calling and streaming capability
are not implied by a successful text task.

| Provider | Model | Initial task checks | Current decision |
| --- | --- | --- | --- |
| gemini | `gemini-3.5-flash-lite` | 4/5 initial checks passed; median successful check 6.94s | Trend commentary and supervisor fallback; excluded from inferential interpretation after a repeated p-value error. |
| gemini | `gemini-3.8-flash` | 4/5 initial checks passed; median successful check 5.59s | Comparison primary; interpretation/answer fallback; transient 503 failover tested. |
| groq | `openai/gpt-oss-120b` | 4/5 initial checks passed; median successful check 9.87s | Supervisor primary; schema/code/answer fallback; excluded from hypothesis routes after a p-value error. |
| nvidia | `z-ai/glm-5.3-flash` | 0/5 initial checks passed; all five requests timed out | Excluded: five non-streaming timeouts and a separate streaming readiness timeout. |
| nvidia | `nvidia/nemotron-3.5-super-vl-120b-a12b` | 5/5 initial checks passed; median successful check 1.93s | Primary schema, EDA, hypothesis and chat; keep fallback for server/network errors. |
| nvidia | `stepfun-ai/step-5-preview` | 5/5 initial checks passed; median successful check 18.26s | Statistical interpretation fallback; slower observed responses. |
| nvidia | `google/diffusiongemma-26b-a4b-it` | 3/5 initial checks passed; median successful check 2.00s | Excluded: plan instruction and p-value failures. |
| nvidia | `openai/gpt-oss-20b` | 4/5 initial checks passed; median successful check 7.98s | Chat-code fallback; one initial connection timeout. |

## 10. Add more models here

| Provider | Display name | Exact API model ID | Key variable/pool name only | Owner-reported working task | Example settings | Test evidence / date |
| --- | --- | --- | --- | --- | --- | --- |
| To add | To add | To verify | Variable name only | To add | To add | Pending |

## References

Local integration: [configuration](backend/config.py),
[provider routing](backend/services/llm_service.py),
[constrained interpreter](backend/tools/analytical_worker.py),
[isolated execution wrapper](backend/tools/python_tool.py).

- [Official Google Gemini model catalog](https://ai.google.dev/gemini-api/docs/models) — checked 18 October 2026; used to resolve the explicit Gemini IDs above. Screenshot names without a resolved ID remain unverified.
- [Official Groq GPT-OSS 120B page](https://console.groq.com/docs/model/openai/gpt-oss-120b).
- [Official NVIDIA Nemotron 3.5 Super VL page](https://build.nvidia.com/nvidia/nemotron-3.5-super-vl-120b-a12b).
- [Official NVIDIA Step 5 Preview page](https://build.nvidia.com/stepfun-ai/step-5-preview).
- [Official NVIDIA DiffusionGemma page](https://build.nvidia.com/google/diffusiongemma-26b-a4b-it).
- Owner-supplied NVIDIA code examples, proposed Gemini workflow table, and model/quota screenshots in this conversation. These are recorded inputs, not independent benchmark results.

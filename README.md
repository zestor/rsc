# Recursive Scaffolded Cognition

This package implements the RSC v2.2 orchestration harness described in [design.md](design.md).

RSC composes explicit state, skill files, memory, role-specific prompts, recursive artifact handling, evaluator grading, and deterministic state writes around OpenAI Responses, OpenAI-compatible chat, or OpenRouter clients.

It also includes:

- `RSCConfig` for validated environment-based runtime configuration.
- OpenRouter and OpenAI LLM backends. The default provider is OpenRouter with `z-ai/glm-5.2`; use `LLM_PROVIDER=openai` only when you want the OpenAI Responses path.
- OpenAI usage supports the Responses API shape for `gpt-5.5`, using developer/user input blocks, text verbosity, reasoning effort, stored responses, and optional include fields.
- `JSONFormatter`, `log_event`, and log summarizers for detailed structured JSON telemetry through standard Python loggers.
- Optional automatic web search context through a markdown-returning `SearchProvider`; set `SEARCH_ENDPOINT` to use the HTTP provider.
- Firecrawl search is supported through `FirecrawlSearchProvider`; put `FIRECRAWL_API_KEY` in `.env`, never in code.
- Skill-aware routing can index the full `code-change-handoff` skill corpus and select top skills with hybrid embedding plus HashingVectorizer-style lexical cosine scoring.
- A root import shim so `import rsc.contracts` works when tools analyze either this project root or the parent `Documents` workspace.

## Install

```bash
python -m pip install -e '.[dev]'
```

## Test

```bash
python -m pytest --cov=rsc --cov-report=term-missing
```

## Live Pipeline Test

The normal suite does not spend API credits. To run the full live OpenRouter + Firecrawl pipeline test, set real credentials in `.env` and opt in:

```bash
RSC_LIVE_TESTS=1 python -m pytest tests/test_live_pipeline.py -m live -s
```

That test performs a real Firecrawl search, routes a real RSC task through OpenRouter for Planner, Critic, Verifier, Reviser, Synthesizer, and Evaluator, then asserts the final output and role outputs are nonempty.

## Detailed Logs

`examples/run_loop.py` configures daily JSONL file logging automatically. By default logs are written to [rsc/logs](rsc/logs) as `rsc-YYYY-MM-DD.jsonl`; when the date changes, new events go to a new daily file. Set `LOG_DIR` to change the folder.

Configure a logger with `JSONFormatter` or `configure_daily_file_logging()` to capture machine-readable execution traces. RSC emits step-level events for session lifecycle, search, skill routing, state loading, role prompts, model outputs, artifact updates, evaluator verdicts, memory distillation/compression, recursion, and final status.

Verbose payloads include full prompt/response/search/state text where available, token estimates, character counts, SHA-256 hashes, previews, rubric labels, selected skill IDs, search counts, role output summaries, verdict details, cumulative token usage, and success/failure flags. API keys and credentials are not logged.

Key events include `session.start`, `search.start`, `search.complete`, `skill.route.start`, `skill.selected`, `state.load.complete`, `role.start`, `role.retry`, `role.complete`, `role.error`, `artifact.update`, `evaluator.start`, `evaluator.complete`, `verdict.complete`, `turn.complete`, `memory.distill.start`, `memory.distill.complete`, `session.complete`, and `session.error`.

## Network Retries

RSC retries transient network operations up to 5 times with staggered backoff delays of 5, 10, 15, 20, and 25 seconds. This applies to model calls, evaluator calls, memory distillation/compression calls, embeddings, OpenRouter/OpenAI adapter calls, Firecrawl/HTTP search calls, and frontend API requests. Non-retryable errors such as authentication, bad request, not found, validation, or content filter failures are not retried.

## Run

```bash
OPENROUTER_API_KEY=... python examples/run_loop.py
```

The default state directory is [state](state). Set `STATE_DIR` to point at another compatible state directory.

## Web UI And API

Build the React UI into the Python package:

```bash
cd ui
npm install
npm run build
```

Start the combined FastAPI + React server from the project root:

```bash
uvicorn rsc.web_api:app --host 127.0.0.1 --port 8000
```

FastAPI serves the React app and its bundled assets from the same process. The UI calls the same server through relative API paths:

- `GET /api/health`
- `GET /api/config`
- `POST /api/runs`
- `POST /api/runs/stream`

Open `http://127.0.0.1:8000/` to use the RSC Console. The UI is a Perplexity-style ask surface with mode/model selectors, file attachments, live activity events, and answer output. The UI does not ask for a skill name; RSC detects intent against configured skill libraries and injects only relevant skill markdown before LLM calls.

`/api/runs/stream` accepts multipart form data:

- `task`: question or instruction
- `mode`: `answer`, `research`, `write`, or `code`
- `model`: model override such as `z-ai/glm-5.2`
- `rubric_json`: JSON list of rubric items
- `files`: markdown/text/PDF/DOCX/CSV/JSON/YAML/RST attachments

Attachments are converted to markdown server-side. PDF conversion uses `pypdf`; DOCX conversion uses `python-docx`; text-like formats are decoded directly. The endpoint streams Server-Sent Events such as `run.accepted`, `attachments.convert.complete`, `log.role.start`, `log.role.complete`, and `rsc.run.complete`.

Default `.env` values for the web app:

```bash
LLM_PROVIDER=openrouter
LOOP_MODEL=z-ai/glm-5.2
EVAL_MODEL=z-ai/glm-5.2
SEARCH_PROVIDER=firecrawl
```

## OpenAI Responses

For current OpenAI usage, keep `LLM_PROVIDER=openai` and set:

```bash
LOOP_MODEL=gpt-5.5
EVAL_MODEL=gpt-5.5
OPENAI_USE_RESPONSES_API=true
OPENAI_TEXT_VERBOSITY=medium
OPENAI_REASONING_EFFORT=medium
OPENAI_REASONING_SUMMARY=auto
OPENAI_STORE=true
OPENAI_INCLUDE=reasoning.encrypted_content,web_search_call.action.sources
```

RSC adapts its internal two-message role prompts to Responses API input blocks by mapping system instructions to the `developer` role and user prompts to the `user` role.

## Firecrawl Search

Create a local `.env` from [.env.example](.env.example) and set:

```bash
FIRECRAWL_API_KEY=...
SEARCH_PROVIDER=firecrawl
SEARCH_MAX_RESULTS=20
SEARCH_MAX_CONCURRENCY=2
```

When configured, RSC automatically searches for each task and injects the returned markdown into role context under `## SEARCH RESULTS`.
`SEARCH_MAX_CONCURRENCY` gates outbound web requests; keep it at `2` for the Firecrawl free plan and raise it only when your plan allows more concurrent requests.

## Skill Routing

Point RSC at one or more skill roots:

```bash
SKILL_LIBRARY_PATHS=../code-change-handoff/skill-details-bundle/skills,../code-change-handoff/design_context/skills,../code-change-handoff/skills
SKILL_TOP_K=3
```

At runtime RSC recursively discovers `SKILL.md` files, checksums them, infers dependencies, resolves readiness as `ready`, `degraded`, or `blocked`, loads declared local references, and injects the selected skill summaries into role context under `## SELECTED SKILLS`.

## OpenRouter

Install the optional SDK dependency:

```bash
python -m pip install -e '.[openrouter]'
```

Then set local `.env` values:

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=...
LOOP_MODEL=z-ai/glm-5.2
EVAL_MODEL=z-ai/glm-5.2
OPENROUTER_PROVIDER_ZDR=false
OPENROUTER_PROVIDER_ONLY=fireworks,wafer,cloudflare,friendli
```

The OpenRouter adapter exposes the same internal `chat.completions.create(...)` shape used by the rest of RSC, so role routing and evaluator behavior stay unchanged.
OpenRouter routing is restricted to `fireworks`, `wafer`, `cloudflare`, and `friendli`; `cloudfare` is accepted in config and normalized to `cloudflare`.
# Requirements Document

## Introduction

The AI Coach backend is at ~70% PRD completion. All critical blockers (RAG pipeline,
RLS enforcement, analytics stub) have been resolved in recent sessions. This spec
covers the remaining high-impact gaps identified in the June 10 engineering report,
grouped into seven work streams:

1. Claude LLM client + engine wiring + prompt caching
2. ScoringEngine call site fix + unit tests
3. arq as primary worker
4. Test coverage (unit + RAG integration + cross-tenant)
5. Frontend role gating + analytics wiring
6. No-answer guard + placeholder score fix
7. Production hardening pass

## Requirements

### 1. Claude LLM Client + Engine Wiring + Prompt Caching

`config.py` already declares `LLM_PROVIDER: Literal["ollama", "claude"]`,
`ANTHROPIC_API_KEY`, and `CLAUDE_MODEL = "claude-haiku-4-5"`. No `claude_client.py`
exists yet and both engines import `OllamaClient` directly.

- **REQ-1.1** A `ClaudeClient` class in `app/ai/claude_client.py` must expose the same interface as `OllamaClient`: `generate(prompt, system, temperature, max_tokens) -> LLMResponse` and `stream_generate(...)`. The response dataclass must be drop-in compatible.

- **REQ-1.2** A `get_llm_client()` factory in `app/ai/llm_factory.py` must return `ClaudeClient` when `settings.LLM_PROVIDER == "claude"` and `OllamaClient` otherwise. Engines must use this factory.

- **REQ-1.3** `ClaudeClient` must implement Anthropic prompt caching (`cache_control`) for the system prompt and static rubric/persona blocks. Cache-hit token counts must be logged at DEBUG level.

- **REQ-1.4** `CoachingEngine` and `ScoringEngine` must accept any `LLMClient` protocol object (not a concrete `OllamaClient`). Constructors must be updated accordingly.

- **REQ-1.5** When `LLM_PROVIDER=claude` and `ANTHROPIC_API_KEY` is None or empty, startup must log a clear warning and fall back to Ollama rather than crashing.

- **REQ-1.6** `.env.example` must document `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, and `CLAUDE_MODEL`.

### 2. ScoringEngine Call Site Fix + Unit Tests

`ScoringEngine._get_scoring_template()` accepts a `module_version` argument but `score_session()` never passes it, so the module's stored template is never used.

- **REQ-2.1** `score_session()` must accept an optional `module_version` argument (or load it internally from a `module_version_id` UUID) and pass it to `_get_scoring_template()`.

- **REQ-2.2** The hardcoded fallback template in `_get_scoring_template()` must remain a genuine last resort only, never the primary path when a module template exists.

- **REQ-2.3** Unit tests in `tests/unit/test_scoring_engine.py` must cover:
  - Rubric weight math: weights summing to 1.0 produce correct weighted scores.
  - Band mapping: score clamping to `[0, max_score]`.
  - Template selection: module version template takes priority over fallback.
  - Parse success: valid JSON scoring response → correct `ScoreDimension` list.
  - Parse failure: malformed JSON → `UnprocessableError` raised (not swallowed).

- **REQ-2.4** All unit tests in REQ-2.3 must run without a database connection.

### 3. arq as Primary Worker

`worker.py` (asyncio, in-process) is the current active path. `queue.py` (arq-based) is fully written but not wired as primary. The asyncio worker loses tasks on process restart.

- **REQ-3.1** Knowledge ingestion endpoints must enqueue via arq when `REDIS_URL` is reachable, falling back to the asyncio worker when Redis is unavailable (e.g. in tests). Fallback must log a warning.

- **REQ-3.2** The arq worker must be startable via `python -m arq app.tasks.queue.WorkerSettings`.

- **REQ-3.3** A `get_arq_pool()` helper in `app/tasks/queue.py` must provide a reusable arq connection pool for the API layer.

- **REQ-3.4** `docker-compose.yml` must include a `worker` service running `python -m arq app.tasks.queue.WorkerSettings`.

- **REQ-3.5** Arq availability detection must not block the hot request path — use a module-level flag set at startup.

### 4. Test Coverage

`tests/unit/` and `tests/integration/` subdirectories exist but are empty. Existing coverage is ~25%.

- **REQ-4.1** `tests/unit/test_scoring_engine.py` — covered by REQ-2.3.

- **REQ-4.2** `tests/unit/test_module_validator.py`:
  - Weights summing to 1.0 → no errors.
  - Weights not summing to 1.0 → error contains "weight".
  - Missing step labels → error per step.
  - Missing template variables → error per template.
  - Empty rubric → error.

- **REQ-4.3** `tests/unit/test_prompt_builder.py`:
  - All known slots resolve correctly.
  - Unknown slots are left as-is.
  - `_format_rubric()` includes dimension names and weights.

- **REQ-4.4** Existing `tests/test_rag_pipeline.py` (5 tests) must pass. Fix any failures.

- **REQ-4.5** Existing `tests/test_tenant_isolation.py` (7 tests) must pass. Fix any failures.

- **REQ-4.6** `tests/integration/test_analytics.py`:
  - `GET /analytics/dashboard` returns 403 for learner role.
  - `GET /analytics/dashboard` returns 200 for tenant_admin with correct shape.
  - `GET /analytics/session-trend` returns list with `date` and `count` keys.

- **REQ-4.7** `tests/integration/test_module_versions.py`:
  - Bad rubric weights → 422 with weight error message.
  - Valid schema → 201 with correct response shape.

### 5. Frontend Role Gating + Analytics Wiring

`App.tsx` wraps `/analytics` and `/admin` in `<RequireRole>`. The Layout nav renders all links regardless of role.

- **REQ-5.1** `Layout.tsx` sidebar must conditionally render admin-only links (`Analytics`, `Knowledge Base`, `Admin`, `Module Builder`) only for admin/superadmin users. Learners see only: Dashboard, Modules, Achievements, Profile.

- **REQ-5.2** `KnowledgeBase` route must be wrapped in `<RequireRole role="admin">` in `App.tsx`.

- **REQ-5.3** The `Analytics.tsx` module performance chart X-axis must display a human-readable module name, not a raw UUID. Use the first 8 chars of UUID as fallback.

- **REQ-5.4** On app mount, roles must be refreshed from `/auth/me` so role changes take effect without full logout/login.

### 6. No-Answer Guard + Placeholder Score Fix

When the knowledge base is empty, the coach has no explicit instruction to acknowledge absence gracefully. `_generate_placeholder_scores` is a risk if ever called accidentally.

- **REQ-6.1** The default coaching prompt template must include an explicit instruction: if `{{knowledge}}` resolves to the "no knowledge found" text, the LLM must fall back to framework general principles and must NOT fabricate citations.

- **REQ-6.2** `CoachingResponse.knowledge_used` must be `True` only when at least one chunk with non-zero similarity was actually retrieved.

- **REQ-6.3** `CoachingEngine._generate_placeholder_scores()` must be removed. Production parse failures must always raise `UnprocessableError`.

- **REQ-6.4** The session feedback endpoint must return HTTP 422 (not 500) on `UnprocessableError`, with a user-readable `detail` that does not expose raw LLM output.

### 7. Production Hardening Pass

The app runs in development mode. A production pass ensures deployment readiness.

- **REQ-7.1** Startup must warn if `SECRET_KEY` is shorter than 64 characters (current minimum is 32).

- **REQ-7.2** `.env.production` must have `DEBUG=False` and `ENVIRONMENT=production`.

- **REQ-7.3** `Dockerfile.backend` must run the app as a non-root user and must not copy `.env` into the image.

- **REQ-7.4** `docker-compose.prod.yml` must use built images (no source volume mounts) with environment from `.env.production`.

- **REQ-7.5** Startup must warn if `ALLOWED_ORIGINS` contains `localhost` in non-development environments.

- **REQ-7.6** File uploads must not be publicly accessible; serving must go through an authenticated endpoint.

- **REQ-7.7** Database pool settings must be tunable via environment and documented in `.env.example`.

- **REQ-7.8** Sentry DSN (`SENTRY_DSN` already in config) must be wired into `main.py` via `sentry_sdk.init()` when set.

- **REQ-7.9** The in-process rate limiter must be supplemented by Redis-backed rate limiting (e.g. `slowapi`) so limits survive restarts and horizontal scaling.

- **REQ-7.10** `pyproject.toml` must have `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`.

## Glossary

- **arq**: async Redis Queue — a Redis-backed background job library for Python async.
- **LLM_PROVIDER**: config flag selecting between `"ollama"` (local) and `"claude"` (Anthropic API).
- **RLS**: PostgreSQL Row Level Security — enforced at the DB layer per tenant.
- **UoW**: Unit of Work — the transaction boundary pattern used throughout the backend.
- **RAG**: Retrieval-Augmented Generation — grounding LLM responses in knowledge base content.
- **GUC**: PostgreSQL Grand Unified Configuration — per-session settings like `app.current_tenant_id`.

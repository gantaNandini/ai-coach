# Technical Design Document — Platform Hardening

## Overview

This document covers the technical design for seven work streams that bring the AI Coach
platform from ~70% to production-ready. Each section describes the concrete change, the
data flow, and the decision rationale. No new external dependencies are introduced unless
explicitly called out.

---

## 1. Claude LLM Client + Engine Wiring + Prompt Caching

### 1.1 LLMClient Protocol

A structural `Protocol` in `app/ai/llm_factory.py` replaces the concrete `OllamaClient`
type annotation in both engines:

```
Protocol LLMClient
  generate(prompt, system, temperature, max_tokens) -> LLMResponse
  stream_generate(prompt, system, temperature, max_tokens) -> AsyncIterator[str]

@dataclass LLMResponse          # shared, drop-in compatible with OllamaResponse
  content: str
  prompt_tokens: int
  completion_tokens: int
  total_tokens: int
  response_time_ms: int
  model_used: str
  cache_read_tokens: int = 0    # populated by ClaudeClient only
  cache_write_tokens: int = 0
```

`OllamaResponse` is aliased to `LLMResponse` so no call sites change.

### 1.2 Factory

```python
# app/ai/llm_factory.py
def get_llm_client() -> LLMClient:
    if settings.LLM_PROVIDER == "claude":
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("[LLM] ANTHROPIC_API_KEY not set — falling back to Ollama")
            return OllamaClient()
        return ClaudeClient()
    return OllamaClient()
```

Both engines call `get_llm_client()` in their constructors. The `ollama_client` parameter
is renamed to `llm_client: LLMClient` with a deprecation alias for the old name.

### 1.3 ClaudeClient — prompt caching

Anthropic's prompt caching attaches `cache_control: {"type": "ephemeral"}` to message
blocks that are static across calls. The system prompt and rubric block qualify; the
learner submission does not.

```
ClaudeClient.generate(prompt, system, temperature, max_tokens)
  messages = [
    {role: "user", content: [
      {type: "text", text: system, cache_control: {"type": "ephemeral"}},  # cached
      {type: "text", text: prompt}                                           # dynamic
    ]}
  ]
  resp = anthropic.messages.create(model=CLAUDE_MODEL, max_tokens, temperature, messages)
  cache_read  = resp.usage.cache_read_input_tokens  or 0
  cache_write = resp.usage.cache_creation_input_tokens or 0
  logger.debug("[CLAUDE] cache read=%d write=%d", cache_read, cache_write)
  return LLMResponse(content=resp.content[0].text, ..., cache_read_tokens, cache_write_tokens)
```

### 1.4 Engine constructor update

```python
# CoachingEngine
def __init__(self, llm_client: LLMClient, prompt_builder, retrieval_service, citation_service):
    self._llm = llm_client   # was self._ollama

# ScoringEngine
def __init__(self, llm_client: LLMClient, prompt_builder):
    self._llm = llm_client
```

All `self._ollama.generate(...)` call sites become `self._llm.generate(...)`.

### 1.5 Startup fallback

`run_startup_checks()` gains a `check_claude()` step that runs when
`LLM_PROVIDER == "claude"`. If `ANTHROPIC_API_KEY` is absent it logs a warning and sets
`startup_status["llm_provider"] = "fallback_ollama"`.

---

## 2. ScoringEngine Call Site Fix

### 2.1 The bug

`score_session()` calls `self._get_scoring_template(rubric)` — never passing
`module_version`. The template stored in `ModulePromptTemplate` is therefore always
ignored and the generic fallback is used.

### 2.2 Fix — pass module_version through score_session

```python
async def score_session(
    self,
    session_id,
    feedback_text,
    rubric,
    intake_data,
    module_version=None,      # ← new optional arg
    rubric_id=None,
    rubric_version=1,
) -> CoachingScoreResponse:
    template = self._get_scoring_template(rubric, module_version)  # ← fix
    ...
```

All callers of `score_session()` that have a `module_version` object already loaded can
pass it. The existing signature is additive — existing callers without it still work via
the fallback.

### 2.3 Template priority

```
_get_scoring_template(rubric, module_version=None)
  if module_version is not None:
    for t in module_version.prompt_templates:
      if t.template_type == "scoring" and t.template_body:
        return t.template_body          # ← primary path
  return FALLBACK_TEMPLATE              # ← last resort only
```

Note: the existing code uses `t.template_text` but the ORM field is `template_body`
(confirmed from `CoachingEngine._load_prompt_template`). Fixed in this pass.

### 2.4 Unit tests — no DB required

All tests use plain Python objects (no SQLAlchemy models, no database):

```
tests/unit/test_scoring_engine.py
  - test_weighted_score_sums_to_100   rubric weights 0.4+0.6 → correct weighted total
  - test_weighted_score_normalized    weights not summing to 1.0 → still 0-100
  - test_score_clamped_to_max         LLM returns score > max_score → clamped
  - test_score_clamped_to_zero        LLM returns negative score → 0
  - test_template_priority            module_version template used over fallback
  - test_template_fallback            no module_version → fallback template returned
  - test_parse_valid_response         valid JSON → ScoreDimension list
  - test_parse_malformed_json         broken JSON → UnprocessableError raised
  - test_parse_missing_dimensions     JSON with no dimensions key → UnprocessableError
```

Fake LLM client is a simple async stub that returns a hardcoded `LLMResponse`.

---

## 3. arq as Primary Worker

### 3.1 Module-level availability flag

```python
# app/tasks/queue.py  (module level)
_arq_available: bool = False

async def init_arq_pool() -> None:
    """Called once from lifespan startup — sets _arq_available flag."""
    global _arq_available, _arq_pool
    try:
        pool = await create_pool(WorkerSettings.redis_settings())
        _arq_pool = pool
        _arq_available = True
        logger.info("[ARQ] Redis pool ready")
    except Exception as exc:
        logger.warning("[ARQ] Redis unavailable — falling back to asyncio worker: %s", exc)
        _arq_available = False
```

`run_startup_checks()` calls `init_arq_pool()`. The flag is read synchronously from the
hot request path — no await, no blocking.

### 3.2 Enqueue helper

```python
# app/tasks/queue.py
async def enqueue(job_name: str, **kwargs) -> None:
    """Enqueue a job via arq if Redis is available, else run inline."""
    if _arq_available and _arq_pool:
        await _arq_pool.enqueue_job(job_name, **kwargs)
    else:
        logger.warning("[ARQ] Fallback — running %s inline", job_name)
        fn = {f.__name__: f for f in WorkerSettings.functions}[job_name]
        await fn(ctx={}, **kwargs)
```

Knowledge ingestion endpoints replace direct `asyncio.create_task()` calls with:
```python
await enqueue("ingest_document", tenant_id=..., source_id=..., ...)
```

### 3.3 get_arq_pool()

```python
def get_arq_pool():
    """Return the module-level arq pool (may be None if Redis unavailable)."""
    return _arq_pool
```

### 3.4 docker-compose.yml worker service

```yaml
redis:
  image: redis:7-alpine
  restart: unless-stopped
  ports: ["6379:6379"]

worker:
  build: { context: ., dockerfile: Dockerfile.backend }
  command: python -m arq app.tasks.queue.WorkerSettings
  environment:
    DATABASE_URL: ...
    REDIS_URL: redis://redis:6379/0
  depends_on: [postgres, redis]
```

`docker-compose.prod.yml` worker command updated from the placeholder echo to:
```
command: python -m arq app.tasks.queue.WorkerSettings
```

---

## 4. Test Coverage

### 4.1 conftest.py additions

```
tests/conftest.py                    — already has some fixtures; extended with:
  fake_llm_client()                  — returns AsyncMock LLMClient stub
  mock_module_version()              — plain Python object with prompt_templates list
  scoring_engine(fake_llm_client)    — ScoringEngine wired with fake LLM
  prompt_builder()                   — real PromptBuilder instance (no DB)
```

### 4.2 Test files

```
tests/unit/
  test_scoring_engine.py             REQ-2.3 / REQ-4.1
  test_module_validator.py           REQ-4.2
  test_prompt_builder.py             REQ-4.3

tests/integration/
  test_analytics.py                  REQ-4.6 — uses TestClient + JWT fixtures
  test_module_versions.py            REQ-4.7 — uses TestClient
```

Existing `tests/test_rag_pipeline.py` and `tests/test_tenant_isolation.py` are fixed
if broken (import paths, missing fixtures).

### 4.3 pyproject.toml

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 5. Frontend Role Gating + Analytics Wiring

### 5.1 Layout.tsx — role-aware nav

The static `navGroups` array is replaced by a computed function:

```tsx
function buildNavGroups(isAdmin: boolean) {
  const base = [
    { label: 'LEARN',    items: [Dashboard, Modules] },
    { label: 'PRACTICE', items: [MySessions] },
    { label: 'INSIGHTS', items: [Achievements] },
    { label: 'ACCOUNT',  items: [Profile, Billing, Settings] },
  ]
  if (isAdmin) {
    base.splice(2, 0, { label: 'KNOWLEDGE', items: [KnowledgeBase] })
    base[2].items.push(Analytics)  // or however structure works
  }
  return base
}
```

Concretely: `Knowledge Base` and `Analytics` nav items render only when `isAdmin` is
true. `useRole()` is called inside `Layout` to get `isAdmin`.

Admin section (`System Admin`, `Module Builder`) already gates on `is_superadmin` — this
is extended to gate on `isAdmin` instead, since `tenant_admin` and `program_owner` should
also see these items.

### 5.2 App.tsx — KnowledgeBase route guard

```tsx
<Route
  path="/knowledge"
  element={
    <ProtectedRoute>
      <RequireRole role="admin"><KnowledgeBase /></RequireRole>
    </ProtectedRoute>
  }
/>
```

### 5.3 Analytics.tsx — human-readable module names

The module performance chart currently labels X-axis by raw UUID. Fix:

```tsx
// fetch module name from /modules/{id} or use modules list already in cache
const moduleName = moduleMap[moduleId]?.title ?? moduleId.slice(0, 8)
```

The modules query is already in scope on the Analytics page or fetched alongside the
analytics data.

### 5.4 Role refresh on mount — App.tsx

```tsx
// App.tsx
const { setAuth, user, accessToken, refreshToken } = useAuthStore()

useEffect(() => {
  if (!user || !accessToken) return
  authApi.me().then(r => {
    // update roles from latest /auth/me response
    setAuth(r.data, accessToken, refreshToken!)
  }).catch(() => {})   // silent — stale roles are better than a crash
}, [])   // runs once on mount
```

---

## 6. No-Answer Guard + Placeholder Score Fix

### 6.1 Default coaching template — no-KB instruction

The `_get_default_coaching_template()` method in `CoachingEngine` gains an explicit
no-knowledge guard in the prompt text:

```
KNOWLEDGE BASE CONTEXT:
{{knowledge}}

IMPORTANT: If the knowledge context above says "No specific knowledge found", base
your feedback on general {{framework}} framework principles only. Do NOT invent
citations, source names, or document references that do not appear above.
```

### 6.2 knowledge_used accuracy

```python
# coaching_engine.py
knowledge_used = any(
    getattr(chunk, "similarity_score", 1.0) > 0
    for chunk in chunks
)
```

Previously `len(chunks) > 0` — this was already partially correct since the retrieval
service filters by `RAG_SCORE_THRESHOLD`, but this makes the intent explicit.

### 6.3 Remove _generate_placeholder_scores

The method is deleted entirely from `CoachingEngine`. Any accidental call sites will
raise `AttributeError` at test time, making the removal verifiable with:

```bash
grep -r "_generate_placeholder_scores" app/ && echo "FOUND" || echo "CLEAN"
```

### 6.4 HTTP 422 on UnprocessableError from feedback endpoint

```python
# routers/feedback.py or sessions.py
@router.post("/sessions/{session_id}/feedback")
async def submit_feedback(...):
    try:
        result = await coaching_engine.generate_feedback(...)
    except UnprocessableError as exc:
        raise HTTPException(
            status_code=422,
            detail="AI feedback could not be generated. Please try again.",
        ) from exc
```

The raw LLM output is never included in the 422 detail — only a safe, user-readable
message. The full output remains in structured logs.

---

## 7. Production Hardening Pass

### 7.1 SECRET_KEY length warning

```python
# startup.py  run_startup_checks()
if len(settings.SECRET_KEY) < 64:
    logger.warning(
        "[STARTUP] SECRET_KEY is %d chars — recommend >= 64 for production",
        len(settings.SECRET_KEY),
    )
```

The pydantic `min_length=32` constraint remains unchanged (fail-fast on obviously short
keys). The 64-char warning is advisory.

### 7.2 .env.production

`DEBUG=False` and `ENVIRONMENT=production` set explicitly. Already present in the file —
verified and left as-is.

### 7.3 Dockerfile.backend — non-root user, no .env

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user before copying source
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY backend/ .

# Remove any accidentally copied .env files
RUN find /app -name ".env" -delete || true

RUN chown -R appuser:appgroup /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.4 docker-compose.prod.yml — built images, no source mounts

Already structured correctly (no `./backend:/app` volume mount on the backend service).
Worker command changed from placeholder to real arq command (covered in Stream 3).

### 7.5 ALLOWED_ORIGINS localhost warning

```python
# startup.py
if settings.ENVIRONMENT != "development":
    for origin in settings.ALLOWED_ORIGINS:
        if "localhost" in origin:
            logger.warning(
                "[STARTUP] ALLOWED_ORIGINS contains localhost in %s environment: %s",
                settings.ENVIRONMENT, origin,
            )
```

### 7.6 Authenticated file serving

Upload files are served via `GET /api/v1/knowledge/files/{source_id}` — an existing
authenticated endpoint. The `uploads/` directory is not mapped to a public Nginx
location. Nginx config `nginx.prod.conf` must not have a `/uploads` static block.

### 7.7 DB pool settings in .env.example

```
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
```

Settings already declared in `config.py`. `.env.example` additions document them.

### 7.8 Sentry wiring

`init_sentry()` already exists in `startup.py` and calls `sentry_sdk.init()`.
`main.py` does not call it directly because `lifespan` calls `run_startup_checks()`
which calls `init_sentry()` first. No change needed — this requirement is already met.
Design note: verify `sentry_sdk` is in `requirements.txt`.

### 7.9 Redis-backed rate limiting with slowapi

```python
# main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,  # Redis-backed; falls back to memory if unavailable
    default_limits=["200/minute"],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
```

The existing in-process `_rate_store` and `_check_rate_limit` are removed from `main.py`.
The `app/core/security/rate_limiter.py` in-process helper is kept for the auth endpoint
as a secondary defense layer (two-layer: slowapi global + per-endpoint check).

### 7.10 pyproject.toml pytest config

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
filterwarnings = ["ignore::DeprecationWarning"]
```

---

## Component Interaction Map

```
Request → CORSMiddleware → RequestIDMiddleware → LoggingMiddleware
        → TenantContextMiddleware → SecurityHeadersMiddleware
        → SlowAPIMiddleware (Redis-backed rate limit)
        → Router handler
             │
             ├─ CoachingEngine(llm_client=get_llm_client())
             │       └─ LLMClient (OllamaClient | ClaudeClient)
             │
             └─ knowledge endpoint
                     └─ enqueue("ingest_document", ...) → arq pool (Redis)
                                                        → asyncio inline (fallback)
```

```
Worker process (python -m arq app.tasks.queue.WorkerSettings)
  ← pulls jobs from Redis
  → run_ingestion → chunk → generate_embeddings → store vectors
  → on failure: write worker_failures dead-letter table
```

```
Frontend (React)
  App mount → GET /auth/me → setAuth(user, roles)
  Layout → useRole() → isAdmin → conditional nav render
  RequireRole(role="admin") guards /analytics, /admin, /knowledge, /modules/new
```

---

## Files Changed / Created

| File | Change |
|------|--------|
| `app/ai/llm_factory.py` | **NEW** — LLMClient protocol + get_llm_client() factory |
| `app/ai/claude_client.py` | **NEW** — ClaudeClient with prompt caching |
| `app/ai/coaching_engine.py` | llm_client refactor, remove placeholder method, no-KB guard |
| `app/ai/scoring_engine.py` | pass module_version to _get_scoring_template, fix template_body |
| `app/tasks/queue.py` | add _arq_available flag, init_arq_pool(), enqueue(), get_arq_pool() |
| `app/core/startup.py` | add SECRET_KEY length warning, ALLOWED_ORIGINS warning, call init_arq_pool |
| `app/main.py` | add slowapi, remove in-process _rate_store |
| `app/api/v1/routers/feedback.py` | catch UnprocessableError → 422 |
| `Dockerfile.backend` | non-root user, remove .env |
| `docker-compose.yml` | add redis + worker services |
| `docker-compose.prod.yml` | fix worker command |
| `backend/.env.example` | document LLM_PROVIDER, ANTHROPIC_API_KEY, DB pool, SENTRY_DSN |
| `frontend/src/App.tsx` | guard /knowledge, role refresh on mount |
| `frontend/src/components/Layout.tsx` | role-aware nav, isAdmin for admin section |
| `frontend/src/pages/Analytics.tsx` | human-readable module names on chart |
| `tests/conftest.py` | fake_llm_client, mock_module_version fixtures |
| `tests/unit/test_scoring_engine.py` | **NEW** |
| `tests/unit/test_module_validator.py` | **NEW** |
| `tests/unit/test_prompt_builder.py` | **NEW** |
| `tests/integration/test_analytics.py` | **NEW** |
| `tests/integration/test_module_versions.py` | **NEW** |
| `pyproject.toml` | pytest asyncio_mode = "auto" |

---

## Correctness Properties

The following properties are validated by the unit and integration test suite:

1. **Weight normalization**: `_compute_weighted_score` always returns a value in `[0, 100]` regardless of whether dimension weights sum to 1.0 or not.

2. **Score clamping**: No dimension score in a `ScoreBreakdown` ever exceeds its `max_score` or falls below 0.

3. **Template priority**: When a module version carries a `scoring`-type prompt template, `_get_scoring_template` must return that template and never the fallback, regardless of what the rubric looks like.

4. **Parse failure propagation**: A malformed LLM JSON response must always surface as `UnprocessableError` — never silently produce a zero-score or placeholder result.

5. **knowledge_used accuracy**: `CoachingResponse.knowledge_used` is `True` if and only if at least one retrieved chunk had a non-zero similarity score.

6. **Role gate completeness**: A request to `/knowledge`, `/analytics`, `/admin`, or `/modules/new` from a learner-only session must receive a redirect to `/dashboard`, never the protected page content.

7. **arq fallback safety**: If Redis is unavailable at startup, ingestion jobs run inline without data loss and without crashing the API process.

8. **Rate limit durability**: Restarting the API process must not reset rate limit counters (enforced by Redis-backed slowapi).

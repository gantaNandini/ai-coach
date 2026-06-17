# AI Coach Platform — Task List
# Current completion: ~88% → Target: 100%
# Work through priorities in order. Check off items as completed.
# Rules: tech-stack.md | Product definition: product.md

---

## PRIORITY 1 — Verify & harden the 3 critical fixes end-to-end
> These were flagged as "fixed" in the last assessment but have not been verified running.
> Do not assume code that exists is working. Check each one.

- [ ] **1.1 RAG ingestion actually runs**
  - Confirm `knowledge.py` router calls `enqueue(run_ingestion, ...)` on text/upload/URL POST
  - Confirm `run_ingestion` correctly chunks and writes `knowledge_chunks` rows
  - Confirm `generate_embeddings_for_source` writes embedding vectors to `knowledge_chunks.embedding`
  - Confirm retrieval returns chunks with non-zero similarity after ingestion
  - Fix anything broken before moving on

- [ ] **1.2 Claude LLM path is active and functional**
  - Confirm `llm_factory.get_llm_client()` returns `ClaudeClient` when `LLM_PROVIDER=claude`
  - Confirm `ClaudeClient` sends requests to Anthropic API with correct model (`claude-sonnet-4-6`)
  - Confirm prompt caching headers are set on system prompt and static rubric blocks
  - Confirm fallback to Ollama when `ANTHROPIC_API_KEY` is missing (logs warning, doesn't crash)
  - Confirm `CoachingEngine` and `ScoringEngine` use `get_llm_client()` — not `OllamaClient()` directly

- [ ] **1.3 Tenant GUC / RLS is enforced on every request**
  - Confirm `UnitOfWork.__aenter__` runs `SET LOCAL app.current_tenant_id = '<uuid>'` before queries
  - Confirm UUID is validated with regex before interpolation (injection guard)
  - Confirm superadmin path sets `app.is_superadmin = 'true'` and bypasses RLS correctly
  - Write a quick smoke test: create two tenants, confirm tenant A cannot read tenant B's KB

---

## PRIORITY 2 — Fix scoring engine template bug + no-fake-scores rule

- [ ] **2.1 ScoringEngine passes `module_version` to `_get_scoring_template`**
  - `score_session()` must accept `module_version=None` and pass it through
  - Confirm the module's stored `ModulePromptTemplate` (type=`scoring`) is actually used
  - Confirm the generic fallback is only hit when no module template exists

- [ ] **2.2 Remove `_generate_placeholder_scores`**
  - Delete the method from `CoachingEngine`
  - Any LLM parse failure must raise `UnprocessableError` — never return fake mid-range scores
  - Verify with: `grep -r "_generate_placeholder_scores" backend/app/` — must return nothing

- [ ] **2.3 HTTP 422 on parse failure (not 500)**
  - Catch `UnprocessableError` in session/feedback endpoints
  - Return HTTP 422 with a safe user-readable message
  - Raw LLM output must never appear in the response body (log it instead)

- [ ] **2.4 No-answer / hallucination guard in coaching prompt**
  - Default coaching prompt template must include explicit instruction:
    if `{{knowledge}}` resolves to "No specific knowledge found", use framework general
    principles only — do NOT fabricate citations or source references
  - `CoachingResponse.knowledge_used` must be `True` only when at least one chunk with
    similarity > 0 was retrieved

---

## PRIORITY 3 — arq worker wired as primary (Redis-backed)

- [ ] **3.1 `init_arq_pool()` called at startup**
  - `app/core/startup.py` must call `init_arq_pool()` in `run_startup_checks()`
  - Sets module-level `_arq_available` flag without blocking the request path
  - Logs clearly: `[ARQ] Redis pool ready` or `[ARQ] Redis unavailable — falling back`

- [ ] **3.2 Knowledge ingestion enqueues to arq when Redis is available**
  - All three source endpoints (text, upload, URL) use `queue.enqueue(...)` not raw `asyncio.create_task`
  - Falls back to asyncio inline worker when `_arq_available = False`
  - Fallback logs a warning

- [ ] **3.3 `docker-compose.yml` has `redis` + `worker` services**
  - `redis: image: redis:7-alpine`
  - `worker: command: python -m arq app.tasks.queue.WorkerSettings`
  - Worker depends on both `postgres` and `redis`

- [ ] **3.4 Worker is startable standalone**
  - `python -m arq app.tasks.queue.WorkerSettings` starts without error
  - Cron job for URL re-crawl is registered (runs hourly)

---

## PRIORITY 4 — Test coverage (target ≥ 70% on critical paths)

- [ ] **4.1 Unit: `tests/unit/test_scoring_engine.py`**
  - Rubric weight math: weights 0.4+0.6 → correct weighted total
  - Score clamped to `[0, max_score]` (never negative, never over max)
  - Module version template takes priority over fallback
  - Valid JSON scoring response → correct `ScoreDimension` list
  - Malformed JSON → `UnprocessableError` raised (not swallowed)
  - All tests run without a DB connection (pure Python objects)

- [ ] **4.2 Unit: `tests/unit/test_module_validator.py`**
  - Weights summing to 1.0 → no errors
  - Weights not summing to 1.0 → error mentions "weight"
  - Missing step labels → error per step
  - Empty rubric → validation error

- [ ] **4.3 Unit: `tests/unit/test_prompt_builder.py`**
  - Known slots (`{{intake}}`, `{{rubric}}`, `{{knowledge}}`) resolve correctly
  - Unknown slots left as-is (no crash)
  - `_format_rubric()` output includes dimension names and weights

- [ ] **4.4 Integration: RAG pipeline test**
  - `tests/test_rag_pipeline.py` (5 tests) must all pass
  - Fix any failures before marking done

- [ ] **4.5 Integration: Cross-tenant isolation test**
  - `tests/test_tenant_isolation.py` (7 tests) must all pass
  - Fix any failures before marking done

- [ ] **4.6 Integration: `tests/integration/test_analytics.py`**
  - `GET /analytics/dashboard` returns 403 for learner role
  - `GET /analytics/dashboard` returns 200 for admin with correct keys
  - `GET /analytics/session-trend` returns list with `date` and `count` keys

- [ ] **4.7 Integration: `tests/integration/test_module_versions.py`**
  - Bad rubric weights → 422 with weight error message
  - Valid schema → 201 with correct response shape

- [ ] **4.8 `pyproject.toml` has `[tool.pytest.ini_options]`**
  - `asyncio_mode = "auto"`
  - `testpaths = ["tests"]`

---

## PRIORITY 5 — Frontend: UI component library + admin gating

- [ ] **5.1 `src/components/ui/` is not empty**
  - Create at minimum: `Button.tsx`, `Card.tsx`, `Input.tsx`, `Modal.tsx`, `Badge.tsx`
  - These replace any inline primitive re-implementations in pages
  - All components must be accessible (proper ARIA, keyboard nav)

- [ ] **5.2 Layout.tsx shows role-aware navigation**
  - Learners see: Dashboard, Modules, Achievements, Profile
  - Admins additionally see: Knowledge Base, Analytics, Admin, Module Builder
  - Uses `useRole()` hook — no hardcoded role strings in JSX

- [ ] **5.3 `/knowledge` route wrapped in `RequireRole role="admin"`**
  - In `App.tsx`, KnowledgeBase route must use `<RequireRole role="admin">`
  - Learner visiting `/knowledge` redirects to `/dashboard`

- [ ] **5.4 Analytics module performance chart uses human-readable names**
  - X-axis shows module name/title, not raw UUID
  - Fallback: first 8 chars of UUID if name not available

- [ ] **5.5 Role refresh on app mount**
  - `App.tsx` calls `GET /auth/me` once on mount and updates auth store with latest roles
  - Silent failure (stale roles better than crash)

---

## PRIORITY 6 — Achievements system wired end-to-end

- [ ] **6.1 `evaluate_achievements` job called after session completion**
  - Confirm the session completion handler enqueues `evaluate_achievements` to arq
  - Job awards achievements based on session count and score thresholds
  - Uses `ON CONFLICT DO NOTHING` (idempotent)

- [ ] **6.2 `Achievements.tsx` page shows real data**
  - Fetches from backend (not hardcoded)
  - Shows awarded badges with date, and locked badges with progress
  - Uses skeleton loading state while fetching

- [ ] **6.3 Points/level displayed on Dashboard or Profile**
  - User's total points and current level visible somewhere in the authenticated UI

---

## PRIORITY 7 — Production hardening

- [ ] **7.1 `Dockerfile.backend` runs as non-root user**
  - `adduser --system appuser` before COPY
  - `USER appuser` before CMD
  - No `.env` files copied into the image (`RUN find /app -name ".env" -delete`)

- [ ] **7.2 `docker-compose.yml` is complete and functional**
  - Services: `postgres`, `redis`, `backend`, `worker`, `frontend`
  - No source volume mounts in `docker-compose.prod.yml`
  - Worker command is `python -m arq app.tasks.queue.WorkerSettings` (not a placeholder)

- [ ] **7.3 Startup warnings**
  - Warn if `SECRET_KEY` < 64 characters
  - Warn if `ALLOWED_ORIGINS` contains `localhost` in non-development environment
  - Warn if `LLM_PROVIDER=claude` but `ANTHROPIC_API_KEY` is missing

- [ ] **7.4 Redis-backed rate limiting via `slowapi`**
  - Replace in-process rate store with `slowapi` using `REDIS_URL` as storage
  - Auth and ingestion endpoints retain their per-endpoint limits
  - Rate limit counters survive API process restart

- [ ] **7.5 File upload security**
  - MIME type validated via magic bytes (not just extension)
  - File size capped before reading full content
  - Uploads not publicly accessible (no static `/uploads` Nginx route)
  - Served only through authenticated endpoint

- [ ] **7.6 `.env.example` is complete**
  - Documents: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `LLM_PROVIDER`, `REDIS_URL`,
    `SECRET_KEY`, `ALLOWED_ORIGINS`, `SENTRY_DSN`, `DATABASE_POOL_SIZE`,
    `DATABASE_MAX_OVERFLOW`, `ENVIRONMENT`

- [ ] **7.7 Sentry wired in `main.py`**
  - `sentry_sdk.init()` called when `SENTRY_DSN` is set
  - `sentry_sdk` in `requirements.txt`

---

## PRIORITY 8 — Final polish and README accuracy

- [ ] **8.1 README reflects reality**
  - Remove claims about SBI/GROW being seeded (they're module data now)
  - Remove claims about RLS "working" if it was broken before
  - Add quickstart: how to run with Docker, how to set `LLM_PROVIDER=claude`

- [ ] **8.2 `citations_visible` tenant setting honoured**
  - If `tenant.settings.citations_visible = false`, citations are stripped from
    feedback reports returned to learners

- [ ] **8.3 Scoring rubric visible in feedback UI**
  - `FeedbackReport.tsx` shows the rubric dimension breakdown, not just the final score
  - Each dimension shows: name, score, max, weight, rationale

- [ ] **8.4 URL re-crawl scheduler running**
  - Confirm arq cron job for `check_url_recrawl` is registered and fires hourly
  - `crawl_frequency` column respected (skip sources not due for re-crawl)

- [ ] **8.5 Frontend bundle verified**
  - All pages use `React.lazy()` (already done in App.tsx — verify none were missed)
  - No single-chunk bundle (confirm Vite output has multiple chunks)

---

## Completion Tracker

| Priority | Description | Status |
|---|---|---|
| P1 | Verify 3 critical fixes end-to-end | ⬜ Not started |
| P2 | Scoring engine + no-fake-scores | ⬜ Not started |
| P3 | arq worker wired as primary | ⬜ Not started |
| P4 | Test coverage ≥ 70% critical paths | ⬜ Not started |
| P5 | Frontend UI library + admin gating | ⬜ Not started |
| P6 | Achievements system end-to-end | ⬜ Not started |
| P7 | Production hardening | ⬜ Not started |
| P8 | Final polish + README | ⬜ Not started |

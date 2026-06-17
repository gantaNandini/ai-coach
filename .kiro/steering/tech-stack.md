# AI Coach Platform — Tech Steering

## Stack (do not change without explicit instruction)

| Layer | Tech |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 async, Alembic |
| DB | PostgreSQL + pgvector (HNSW index on embeddings) |
| Background jobs | arq (primary) or FastAPI BackgroundTasks (quick tasks only) |
| Frontend | React 18, Vite, Zustand, React Query, TypeScript |
| Auth | JWT (access + refresh with rotation), bcrypt |
| LLM | Anthropic API (`claude-sonnet-4-6` for generation) |
| Embeddings | `text-embedding-3-small` or compatible |
| Reranker | `BAAI/bge-reranker-base` (local) or Claude Haiku 4.5 |
| Containerisation | Docker + docker-compose |

---

## Absolute Rules

### Backend

- **Every async DB session MUST set the tenant GUC.** In `UnitOfWork.__aenter__`, always run `SET LOCAL app.current_tenant_id = '<uuid>'` before any query. Validate it is a valid UUID first. Never skip this.

- **RLS is the last line of defence, not the only one.** Also filter by `tenant_id` at the repository layer — defence in depth.

- **Background tasks go through arq.** `BackgroundTasks.add_task` is OK for fire-and-forget within a request; for retryable work (ingestion, embedding, re-crawl) always enqueue to the arq queue (`queue.py`).

- **Never generate placeholder/fake scores.** If the LLM call fails, mark the report `status='failed'` and surface the error. Do not fabricate mid-range scores.

- **"Modules as data" must hold.** `ScoringEngine._get_scoring_template()` must always read from `module_version.prompt_templates`. No hardcoded framework strings anywhere in the engine.

- **File uploads:** validate MIME type + magic bytes, cap size before reading, sandbox PDF/docx/pptx parsing, store outside web root.

- **Rate-limit auth and ingestion endpoints.**

### Frontend

- **`RequireRole` wraps every admin route.** `/analytics`, `/admin`, `/modules/new` and any new admin pages must use the `RequireRole` component + `useRole` hook.

- **No re-implementing primitives inline.** All buttons, modals, cards, inputs go in `src/components/ui/`. If the component doesn't exist, create it there first.

- **Route-level code splitting** via `React.lazy()` + `Suspense` on every page. No single-bundle builds.

- **Never render stub/fake data in a production component.** If data isn't ready, show a skeleton or loading state — never hardcoded numbers.

- **Token auto-refresh interceptor must wrap all API calls.** Never let a 401 reach the user.

---

## Testing (target ≥ 70% on critical paths)

- Unit test: rubric evaluator weight maths and band mapping
- Integration test: full RAG flow — ingest → embed → retrieve → assert citations returned
- Integration test: cross-tenant isolation — tenant A cannot read tenant B's KB / sessions
- Auth end-to-end test (already exists, keep it)
- All tests must pass in CI before merge

---

## File Conventions

```
backend/
  app/
    models/        # SQLAlchemy models only
    schemas/       # Pydantic schemas only
    services/      # Business logic
    repositories/  # DB queries (always filter tenant_id)
    tasks/         # Background task functions (called by arq workers)
    ai/            # LLM clients, coaching engine, scoring engine, RAG
    rag/           # Retrieval, reranker, embedding
  alembic/versions/

frontend/
  src/
    components/ui/ # Reusable primitives (Button, Modal, Card, Input…)
    components/    # Feature components
    pages/         # Route-level pages (all lazy-loaded)
    hooks/         # Custom hooks incl. useRole
    stores/        # Zustand stores
```

---

## Environment Variables Required in Production

```
DATABASE_URL
ANTHROPIC_API_KEY
LLM_PROVIDER=claude
REDIS_URL          # for arq
SECRET_KEY
ALLOWED_ORIGINS
```

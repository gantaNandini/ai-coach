# AI Coach Platform

Multi-tenant AI coaching SaaS. Organizations create coaching modules with custom rubrics, upload knowledge bases, and run AI-powered coaching sessions with grounded, citation-backed feedback.

## Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy 2.0 async (asyncpg), Alembic
- **Database**: PostgreSQL 16 + pgvector, Row Level Security enforced
- **AI**: Ollama (default) or Claude API, sentence-transformers embeddings, cross-encoder reranker
- **Queue**: arq + Redis (durable background jobs)
- **Frontend**: React 18, Vite, Zustand, React Query, Tailwind CSS, recharts
- **Storage**: Local disk (dev) or S3-compatible (prod, set `STORAGE_BACKEND=s3`)
- **Email**: Resend or Postmark (set `EMAIL_PROVIDER`)
- **Billing**: Stripe (set `STRIPE_SECRET_KEY`)
- **Observability**: Sentry (set `SENTRY_DSN`), structured JSON logging, startup health checks

## Quick Start (Local Dev)

### 1. Start dependencies

```bash
docker-compose up -d
```

Starts: PostgreSQL (pgvector/pgvector:pg16), Redis, MinIO.

### 2. Configure environment

```bash
cd backend
cp .env.example .env
# Fill in required values: SECRET_KEY, DATABASE_URL, REDIS_URL
```

### 3. Run migrations

```bash
python -m alembic upgrade head
```

13 migrations run cleanly from scratch (001 → 013). No manual steps required.

### 4. Seed a module (optional)

```bash
python seed_module_complete.py
```

Or use the **no-code Module Builder UI** at `/modules/new` (admin only).

### 5. Start backend

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Start arq worker (required for ingestion, embeddings, re-crawl)

```bash
python -m arq app.tasks.queue.WorkerSettings
```

### 7. Start frontend

```bash
cd ../frontend
npm install
npm run dev
```

## Environment Variables

See `.env.example` for all variables with descriptions.

Key required variables:
- `SECRET_KEY` — JWT signing key, minimum 32 chars
- `DATABASE_URL` — PostgreSQL async DSN (`postgresql+asyncpg://...`)
- `REDIS_URL` — Redis DSN (default: `redis://localhost:6379/0`)

LLM configuration:
- `LLM_PROVIDER=ollama` (default) or `LLM_PROVIDER=claude`
- `OLLAMA_BASE_URL` / `OLLAMA_MODEL` for Ollama
- `ANTHROPIC_API_KEY` / `CLAUDE_MODEL` for Claude
- **Switch trigger**: >5,000 sessions/month (see `docs/decisions/ADR-001-llm-provider.md`)

## Architecture

### Tenant Isolation (RLS)
- **Row Level Security is enforced at the DB layer** via PostgreSQL GUC `app.current_tenant_id`
- Migration 012 applies `FORCE ROW LEVEL SECURITY` to all 18 tenant-scoped tables
- UnitOfWork sets the GUC using validated string interpolation (no bind params — asyncpg limitation)
- Verified by `test_tenant_isolation.py` (6 tests) and live cross-tenant API test

### Background Jobs (arq)
All jobs carry `tenant_id` and pass it to `UnitOfWork(tenant_id=...)`:
- `ingest_document` — chunk and store uploaded/pasted/crawled content
- `generate_embeddings` — embed chunks (3-phase: fetch → inference → write, no DB held during inference)
- `crawl_url` — re-crawl URL sources
- `evaluate_achievements` — award achievements after session completion
- `send_notification_email` — transactional email via Resend/Postmark
- `check_url_recrawl` — hourly cron, enqueues crawl_url for due sources

### RAG Pipeline
1. Document → chunks (512 tokens, 64 overlap)
2. Chunks → embeddings via `BAAI/bge-small-en-v1.5` (384-dim)
3. HNSW vector search (pgvector) or full-text fallback
4. Cross-encoder reranking (`BAAI/bge-reranker-base`, runs in thread executor)
5. Citations attached to feedback report

### Analytics
Real SQL aggregations — no stub data:
- `GET /analytics/dashboard?days=30` — sessions, completion rate, avg score, active users
- `GET /analytics/session-trend?days=30` — daily session counts for line chart
- `GET /analytics/module-performance` — per-module stats

## Test Suite

```bash
pytest tests/ -v
```

**21 tests, all pass:**
- `test_auth.py` — auth endpoints (3)
- `test_auth_flow.py` — login/register/refresh flows (5)
- `test_health.py` — health endpoint (1)
- `test_rag_pipeline.py` — ingest → embed → retrieve (5)
- `test_tenant_isolation.py` — cross-tenant RLS isolation (6)
- `test_audit_log.py` — audit log writes (1)

## Verify RLS is working

```bash
python phase0_verify3.py
```

Expected:
- `Chunks visible WITHOUT setting tenant GUC: 0` ✓
- `Chunks visible with FAKE tenant: 0` ✓
- `Chunks visible with REAL tenant: N > 0` ✓

## Production Deployment

```bash
# Build
docker-compose -f docker-compose.prod.yml build

# Migrate
docker-compose -f docker-compose.prod.yml run --rm backend python -m alembic upgrade head

# Start
docker-compose -f docker-compose.prod.yml up -d

# Health check
curl https://yourdomain.com/health
```

See `docs/RUNBOOK.md` for full operations guide including rollback, backup/restore, and secret rotation.

## What's included

- ✅ Coaching session lifecycle (create → intake → AI feedback → score)
- ✅ Roleplay sessions with AI personas
- ✅ Knowledge base management (paste, upload, URL crawl)
- ✅ RAG-grounded feedback with citations
- ✅ No-code Module Builder UI (admin only, `/modules/new`)
- ✅ Real analytics dashboard with date range selector
- ✅ Role-based UI gating (admin vs learner)
- ✅ Audit logging (login, KB create/delete, session events)
- ✅ Plan limits enforced server-side (max KBs, max sessions/month)
- ✅ File upload validation (magic bytes, returns 415 on spoofed files)
- ✅ Rate limiting (auth: 20/min, general: 200/min)
- ✅ Stripe billing integration (set `STRIPE_SECRET_KEY`)
- ✅ URL re-crawl scheduler (arq cron, hourly)
- ✅ `citations_visible` tenant setting honoured in feedback UI
- ✅ S3-compatible storage abstraction
- ✅ Sentry error tracking

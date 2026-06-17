AI Coach Platform
Multi-tenant AI coaching SaaS. Organisations create coaching modules with custom rubrics, upload knowledge bases, and run AI-powered sessions with grounded, citation-backed feedback.

Status: Production-ready MVP — 29/29 API endpoint tests passing, Docker stack fully operational.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL 16 + pgvector (HNSW index), Row Level Security enforced |
| AI | Ollama (default, local) or Anthropic Claude API |
| Embeddings | `BAAI/bge-small-en-v1.5` (384-dim, CPU-only) |
| Reranker | `BAAI/bge-reranker-base` (local cross-encoder) |
| Queue | arq + Redis (durable background jobs, retry, dead-letter table) |
| Frontend | React 18, Vite, TypeScript, Zustand, React Query, Tailwind CSS |
| Storage | Local disk (dev) or S3-compatible (prod) |
| Email | Resend or Postmark |
| Billing | Stripe |
| Observability | Sentry, structured JSON logging, startup health checks |

---

## Quick Start (Docker)

### 1. Clone and configure

```bash
git clone https://github.com/gantaNandini/ai-coach.git
cd ai-coach
cp backend/.env.example backend/.env
Edit backend/.env — minimum required:

Open `backend/.env` and set the minimum required values:

```env
SECRET_KEY=your-random-64-char-string-here
LLM_PROVIDER=ollama
OLLAMA_MODEL=gemma2:2b
```

### 2. Start services

**Full stack with Ollama (local AI — ~3.2 GB image download on first run):**
```bash
docker-compose up -d
Without Ollama (faster start for testing, falls back gracefully):

**Faster start without Ollama (good for testing / CI):**
```bash
docker-compose -f docker-compose.noollama.yml up -d
Services started: postgres, redis, backend, worker, frontend, ollama (full stack only).

### 3. Run database migrations

```bash
docker exec ai-coach-backend-1 alembic upgrade head
```

13 migrations run automatically (001 → 013). No manual SQL needed.

### 4. Pull an AI model (Ollama stack only)

```bash
# Once the Ollama container is up:
docker exec ai-coach-ollama-1 ollama pull gemma2:2b
gemma2:2b is recommended — fast, small (~1.7GB), good quality. Update OLLAMA_MODEL=gemma2:2b in .env.

`gemma2:2b` is recommended — ~1.7 GB, fast, good quality.

### 5. Seed test data

```bash
docker cp seed_test_tenant.sql ai-coach-postgres-1:/tmp/s1.sql
docker exec ai-coach-postgres-1 psql -U aicoach -d aicoach -f /tmp/s1.sql

docker cp seed_module.sql ai-coach-postgres-1:/tmp/s2.sql
docker exec ai-coach-postgres-1 psql -U aicoach -d aicoach -f /tmp/s2.sql
Or use the no-code Module Builder UI at http://localhost:5173/modules/new (admin only).

Or create modules in-app using the **Module Builder** at `http://localhost:5173/modules/new` (admin only).

### 6. Open the app

| URL | Description |
|---|---|
| http://localhost:5173 | Frontend |
| http://localhost:8000/docs | API docs (Swagger) |
| http://localhost:8000/api/v1/monitoring/health | Health check (requires auth) |

---

## Local Development (no Docker)

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Worker (separate terminal)
python -m arq app.tasks.queue.WorkerSettings

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
Environment Variables
Full reference in backend/.env.example. Key variables:

---

## Environment Variables

Full list in `backend/.env.example`. Essential ones:

```env
# Required
SECRET_KEY=                     # min 64 chars in production
DATABASE_URL=postgresql+asyncpg://aicoach:aicoach@localhost:5432/aicoach
REDIS_URL=redis://localhost:6379/0

# LLM — choose one
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:2b

# — or —
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-5

# Optional
STRIPE_SECRET_KEY=              # billing
SENTRY_DSN=                     # error tracking
STORAGE_BACKEND=local           # or s3
```

---

## Architecture

### Modules as Data
Every coaching framework (SBI, GROW, STAR, custom) is a database record — no Python logic hardcoded per framework. A `CoachingModule` has an immutable `ModuleVersion` which carries the intake schema, scoring rubric, framework steps, prompt templates, and personas. The coaching engine reads these records directly.

### Tenant Isolation (RLS)
- PostgreSQL Row Level Security enabled and **forced** on all 18 tenant-scoped tables
- `UnitOfWork.__aenter__` runs `SET LOCAL app.current_tenant_id = '<uuid>'` before every query
- UUID validated with a strict regex before interpolation — injection-safe
- Superadmin bypass via `SET LOCAL app.is_superadmin = 'true'`
- Migration 012 applies `FORCE ROW LEVEL SECURITY` so the table owner cannot bypass it

### RAG Pipeline
1. Document → chunks (512 tokens, 64 overlap) via `langchain-text-splitters`
2. Chunks → embeddings via `BAAI/bge-small-en-v1.5` (384-dim, CPU)
3. HNSW vector search via pgvector (degrades to full-text search if unavailable)
4. Cross-encoder reranking via `BAAI/bge-reranker-base` (runs in thread executor — non-blocking)
5. Top chunks injected as `{{knowledge}}` into the coaching prompt
6. Citations attached to feedback report with relevance percentages

### Background Jobs (arq + Redis)

| Job | Trigger | What it does |
|---|---|---|
| `ingest_document` | Source creation | Chunk and store pasted / uploaded / crawled content |
| `generate_embeddings` | After ingestion | Embed chunks (3-phase: fetch → CPU inference → write) |
| `crawl_url` | Manual or cron | Re-crawl a URL source |
| `evaluate_achievements` | Session completion | Award badges based on count / score thresholds |
| `send_notification_email` | Events | Transactional email via Resend / Postmark |
| `check_url_recrawl` | Hourly cron | Queue sources due for re-crawl |

Falls back to asyncio inline execution when Redis is unavailable (tests / local dev without Redis).

### LLM Switching
`LLM_PROVIDER=ollama` or `LLM_PROVIDER=claude` — no code changes. If Claude is selected but `ANTHROPIC_API_KEY` is blank the app automatically falls back to Ollama and logs a warning.

CoachingModule → ModuleVersion (immutable, versioned)
ModuleVersion carries: intake_schema (dynamic form), scoring_rubric, ModuleFrameworkStep[], ModulePromptTemplate[], ModulePersona[]
The coaching engine reads these records directly — SBI, GROW, STAR, or any custom framework work identically
API Reference
Base URL: http://localhost:8000/api/v1

## API Overview

Base URL: `http://localhost:8000/api/v1` — full interactive docs at `/docs`.

| Area | Key endpoints |
|---|---|
| Auth | `POST /auth/register` `/auth/login` `/auth/refresh` `/auth/logout` `GET /auth/me` |
| Users | `GET /PATCH /DELETE /users/me` |
| Modules | `GET /POST /modules/` · `POST /modules/{id}/versions` · `POST /modules/{id}/versions/{vid}/publish` |
| Sessions | `POST /GET /sessions/coaching` · `POST /sessions/coaching/{id}/complete` |
| Roleplay | `POST /GET /sessions/roleplay` · `POST /sessions/roleplay/{id}/turn` |
| Knowledge | `GET /POST /knowledge/` · `POST /knowledge/{id}/sources/text\|upload\|url` |
| Feedback | `GET /feedback/{id}` · `POST /feedback/{id}/rate` |
| Progress | `GET /progress/` · `/progress/achievements` · `/progress/achievements/mine` |
| Analytics | `GET /analytics/dashboard` · `/session-trend` · `/module-performance` |
| Billing | `GET /billing/plans` · `POST /billing/checkout` |
| Monitoring | `GET /monitoring/health` · `/monitoring/tasks` |

---

## Running Tests

### Live endpoint test suite

Requires the stack to be running.

```bash
powershell -ExecutionPolicy Bypass -File test_platform.ps1
Expected output: TOTAL: 29 PASSED / 0 FAILED

Expected: `TOTAL: 29 PASSED / 0 FAILED`

Covers: auth, users, modules, sessions, knowledge base ingestion, progress, analytics, monitoring, frontend.

### Unit + integration tests

```bash
cd backend
pytest tests/ -v
```

Covers: auth flows, RAG pipeline (ingest → embed → retrieve → assert citations), cross-tenant RLS isolation, scoring engine rubric maths.

---

## Production Deployment

```bash
# Copy and edit production env
cp backend/.env.example backend/.env.production
# Set: ENVIRONMENT=production, DEBUG=false, long SECRET_KEY, real DB/Redis URLs

# Build
docker-compose -f docker-compose.prod.yml build

# Migrate
docker-compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Start
docker-compose -f docker-compose.prod.yml up -d

# Health check
curl -H "Authorization: Bearer $TOKEN" https://yourdomain.com/api/v1/monitoring/health
Expected: "ready": true, all components "ok".

See `docs/RUNBOOK.md` for rollback, backup/restore, and secret rotation procedures.

---

## Features

- ✅ Coaching session lifecycle — dynamic intake form → AI feedback → rubric scores
- ✅ Roleplay sessions with AI personas (turn-based, emotion/phase tracking)
- ✅ Knowledge base — paste text, upload PDF/DOCX/PPTX/TXT/MD, crawl URLs
- ✅ RAG-grounded feedback with source citations and relevance scores
- ✅ No-code Module Builder (6-step wizard, admin only)
- ✅ Real analytics dashboard with date range selector
- ✅ Role-based UI — admin nav vs learner nav via `RequireRole` + `useRole`
- ✅ Tenant RLS enforced at PostgreSQL level (not just app-layer filtering)
- ✅ Audit logging — session events, KB operations, admin actions
- ✅ Plan limits enforced server-side (max KBs, max sessions/month)
- ✅ File upload security — magic byte validation, size cap, 415 on spoofed types
- ✅ Rate limiting — auth 20/min per IP, general 200/min
- ✅ arq background job queue with retry, dead-letter table, cron scheduler
- ✅ Stripe billing integration
- ✅ Achievements and gamification (points, badges, leaderboards)
- ✅ Token auto-refresh interceptor — 401s never reach the user
- ✅ Dark / light mode
- ✅ S3-compatible storage abstraction
- ✅ Sentry error tracking

---

## Project Structure

```text
ai-coach/
├── backend/
│   ├── app/
│   │   ├── ai/              # LLM clients, coaching engine, scoring engine
│   │   ├── api/v1/routers/  # FastAPI route handlers
│   │   ├── core/            # Config, security, startup checks
│   │   ├── database/        # Engine, UnitOfWork (tenant GUC enforcement)
│   │   ├── middleware/      # Tenant context, logging, rate limiting, security headers
│   │   ├── models/          # SQLAlchemy models
│   │   ├── rag/             # Chunking, embedding, retrieval, reranker, citations
│   │   ├── repositories/    # DB queries — always filtered by tenant_id
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── services/        # Business logic
│   │   └── tasks/           # arq background jobs
│   ├── alembic/versions/    # 13 migrations (001–013)
│   ├── scripts/             # Utility scripts (db checks, seeding helpers)
│   └── tests/               # unit/, integration/, eval/
├── frontend/
│   └── src/
│       ├── components/
│       │   └── ui/          # Button, Input, Card, Badge, Modal
│       ├── hooks/           # useRole, usePageTitle
│       ├── lib/             # axios API client with auth interceptor
│       ├── pages/           # Route-level pages (all lazy-loaded)
│       ├── stores/          # Zustand: auth, theme
│       └── types/           # TypeScript interfaces
├── docs/                    # Architecture decisions (ADRs), runbook
├── nginx/                   # Production nginx config
├── docker-compose.yml           # Full stack (with Ollama)
├── docker-compose.noollama.yml  # Dev / CI stack (no Ollama)
├── docker-compose.prod.yml      # Production stack
├── Dockerfile.backend
├── Dockerfile.frontend
├── seed_module.sql              # SBI Feedback module seed data
├── seed_test_tenant.sql         # Test tenant + admin user seed
└── test_platform.ps1            # 29 live endpoint tests
```

## Contributing

1. Create a branch from `main`
2. All 29 live tests must pass: `powershell -ExecutionPolicy Bypass -File test_platform.ps1`
3. No hardcoded stub/fake data in production components — use loading skeletons
4. Every new admin route must be wrapped in `<RequireRole role="admin">`
5. Every async DB session must go through `UnitOfWork(tenant_id=...)` — never bypass RLS

# AI Coach Platform

Multi-tenant AI coaching SaaS. Organisations create coaching modules with custom rubrics, upload knowledge bases, and run AI-powered sessions with grounded, citation-backed feedback.

> **Status:** Production-ready MVP — 29/29 API endpoint tests passing, Docker stack fully operational.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL 16 + pgvector (HNSW), Row Level Security enforced |
| AI | Ollama (default, local) or Anthropic Claude API |
| Embeddings | `BAAI/bge-small-en-v1.5` (384-dim, CPU) |
| Reranker | `BAAI/bge-reranker-base` (local cross-encoder) |
| Queue | arq + Redis (durable background jobs, retry, dead-letter) |
| Frontend | React 18, Vite, TypeScript, Zustand, React Query, Tailwind CSS |
| Storage | Local disk (dev) or S3-compatible (prod) |
| Email | Resend or Postmark |
| Billing | Stripe |
| Observability | Sentry, structured JSON logging, startup health checks |

---

## Quick Start (Docker — recommended)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/ai-coach.git
cd ai-coach
cp backend/.env.example backend/.env
```

Edit `backend/.env` — minimum required:

```env
SECRET_KEY=your-random-64-char-secret-here
LLM_PROVIDER=ollama          # or 'claude' (needs ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=            # only if LLM_PROVIDER=claude
```

### 2. Start all services

**With Ollama (local AI, ~3.2GB download on first run):**

```bash
docker-compose up -d
```

**Without Ollama (faster start for testing, falls back gracefully):**

```bash
docker-compose -f docker-compose.noollama.yml up -d
```

Services started: `postgres`, `redis`, `backend`, `worker`, `frontend`, `ollama` (full stack only).

### 3. Run database migrations

```bash
docker exec ai-coach-backend-1 alembic upgrade head
```

13 migrations run cleanly (001 → 013). No manual steps required.

### 4. Pull an AI model (Ollama only)

```bash
# Wait for Ollama container to start, then:
docker exec ai-coach-ollama-1 ollama pull gemma2:2b
```

`gemma2:2b` is recommended — fast, small (~1.7GB), good quality. Update `OLLAMA_MODEL=gemma2:2b` in `.env`.

### 5. Seed a test module

```bash
docker cp seed_test_tenant.sql ai-coach-postgres-1:/tmp/s1.sql
docker exec ai-coach-postgres-1 psql -U aicoach -d aicoach -f /tmp/s1.sql

docker cp seed_module.sql ai-coach-postgres-1:/tmp/s2.sql
docker exec ai-coach-postgres-1 psql -U aicoach -d aicoach -f /tmp/s2.sql
```

Or use the **no-code Module Builder UI** at `http://localhost:5173/modules/new` (admin only).

### 6. Open the app

- **Frontend:** http://localhost:5173
- **API docs:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/api/v1/monitoring/health (requires auth)

---

## Local Development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Worker (separate terminal)
python -m arq app.tasks.queue.WorkerSettings

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Environment Variables

Full reference in `backend/.env.example`. Key variables:

```env
# Required
SECRET_KEY=                    # min 64 chars in production
DATABASE_URL=postgresql+asyncpg://aicoach:aicoach@localhost:5432/aicoach
REDIS_URL=redis://localhost:6379/0

# LLM — pick one
LLM_PROVIDER=ollama             # local Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:2b

LLM_PROVIDER=claude             # Anthropic API
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-5

# Optional services
STRIPE_SECRET_KEY=              # billing
SENTRY_DSN=                     # error tracking
STORAGE_BACKEND=local           # or 's3'
```

---

## Architecture

### Tenant Isolation (RLS)
- PostgreSQL Row Level Security enforced on all 18 tenant-scoped tables
- `UnitOfWork.__aenter__` sets `SET LOCAL app.current_tenant_id = '<uuid>'` before every query
- UUID is validated with a strict regex before interpolation (injection-safe)
- Migration 012 applies `FORCE ROW LEVEL SECURITY` — table owner cannot bypass
- Superadmin path sets `app.is_superadmin = 'true'` for cross-tenant admin operations

### Background Jobs (arq + Redis)
All jobs carry `tenant_id` passed to `UnitOfWork(tenant_id=...)`:

| Job | Trigger | Description |
|---|---|---|
| `ingest_document` | Source creation endpoint | Chunk and store uploaded/pasted/crawled content |
| `generate_embeddings` | After ingestion | Embed chunks via sentence-transformers (3-phase: fetch → inference → write) |
| `crawl_url` | Manual or cron | Re-crawl URL sources |
| `evaluate_achievements` | Session completion | Award badges based on session count and score |
| `send_notification_email` | Various events | Transactional email via Resend/Postmark |
| `check_url_recrawl` | Hourly cron | Enqueue crawl_url for sources due for refresh |

Falls back to asyncio inline execution when Redis is unavailable (dev/testing).

### RAG Pipeline
1. Text → chunks (512 tokens, 64 overlap) via `langchain-text-splitters`
2. Chunks → embeddings via `BAAI/bge-small-en-v1.5` (384-dim)
3. HNSW vector search via pgvector (falls back to full-text search if pgvector unavailable)
4. Cross-encoder reranking via `BAAI/bge-reranker-base` (runs in thread executor — non-blocking)
5. Top chunks injected as `{{knowledge}}` in coaching prompt
6. Citations attached to feedback report with relevance scores

### LLM Provider Switching
Set `LLM_PROVIDER` in `.env` — no code changes needed:
- `ollama` → uses local Ollama (free, private, slower)
- `claude` → uses Anthropic API (paid, fast, higher quality)

If `LLM_PROVIDER=claude` but `ANTHROPIC_API_KEY` is blank, it automatically falls back to Ollama and logs a warning.

See `docs/decisions/ADR-001-llm-provider.md` for the full decision rationale.

### Modules as Data
Every coaching framework is a database record — no Python logic hardcoded per framework:
- `CoachingModule → ModuleVersion` (immutable, versioned)
- `ModuleVersion` carries: `intake_schema` (dynamic form), `scoring_rubric`, `ModuleFrameworkStep[]`, `ModulePromptTemplate[]`, `ModulePersona[]`
- The coaching engine reads these records directly — SBI, GROW, STAR, or any custom framework work identically

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

Full interactive docs at `/docs` (Swagger) or `/redoc`.

| Area | Endpoints |
|---|---|
| Auth | POST /auth/register, /auth/login, /auth/refresh, /auth/logout, /auth/me, /auth/change-password |
| Users | GET/PATCH /users/me, DELETE /users/me |
| Modules | GET/POST /modules/, GET/PATCH /modules/{id}, POST /modules/{id}/versions |
| Sessions | POST/GET /sessions/coaching, POST /sessions/coaching/{id}/complete |
| Roleplay | POST/GET /sessions/roleplay, POST /sessions/roleplay/{id}/turn |
| Knowledge | GET/POST /knowledge/, POST /knowledge/{id}/sources/text\|upload\|url |
| Feedback | GET /feedback/{id}, POST /feedback/{id}/rate |
| Progress | GET /progress/, GET /progress/achievements, GET /progress/achievements/mine |
| Analytics | GET /analytics/dashboard, /session-trend, /module-performance |
| Billing | GET /billing/plans, /billing/subscription, POST /billing/checkout |
| Monitoring | GET /monitoring/health, /monitoring/tasks |

---

## Running Tests

### Live endpoint test suite (requires running stack)

```bash
powershell -ExecutionPolicy Bypass -File test_platform.ps1
```

Expected output: `TOTAL: 29 PASSED / 0 FAILED`

### Unit + integration tests

```bash
cd backend
pytest tests/ -v
```

Tests cover:
- Auth flows (register, login, refresh, JWT)
- RAG pipeline (ingest → embed → retrieve → citations)
- Cross-tenant RLS isolation (tenant A cannot read tenant B's data)
- Scoring engine (rubric weight maths, band mapping, template priority)
- Analytics endpoints (role gating, response shape)

---

## Production Deployment

### Build and start

```bash
# Set production env vars
cp backend/.env.example backend/.env.production
# Edit .env.production — set ENVIRONMENT=production, DEBUG=false, real SECRET_KEY

# Build images
docker-compose -f docker-compose.prod.yml build

# Run migrations
docker-compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Start
docker-compose -f docker-compose.prod.yml up -d
```

### Health check

```bash
curl -H "Authorization: Bearer $TOKEN" https://yourdomain.com/api/v1/monitoring/health
```

Expected: `"ready": true`, all components `"ok"`.

See `docs/RUNBOOK.md` for full operations guide — rollback, backup/restore, secret rotation, scaling.

---

## Feature Checklist

- ✅ Coaching session lifecycle (create → dynamic intake → AI feedback → score)
- ✅ Roleplay sessions with AI personas (turn-based, emotion state tracking)
- ✅ Knowledge base management (paste text, upload PDF/DOCX/PPTX/TXT, URL crawl)
- ✅ RAG-grounded feedback with source citations and relevance scores
- ✅ No-code Module Builder UI (admin only, 6-step wizard)
- ✅ Real analytics dashboard with date range selector (no stub data)
- ✅ Role-based UI gating (admin nav vs learner nav)
- ✅ Tenant RLS enforced at PostgreSQL level — not just application filtering
- ✅ Audit logging (session events, KB operations, admin actions)
- ✅ Plan limits enforced server-side (max KBs, max sessions/month)
- ✅ File upload security (magic byte validation, size cap before read, 415 on spoofed types)
- ✅ Rate limiting (auth: 20/min per IP, ingestion: rate-limited)
- ✅ Stripe billing integration
- ✅ URL re-crawl scheduler (arq cron, hourly)
- ✅ Achievements and gamification (points, badges, leaderboards)
- ✅ Token auto-refresh interceptor (401s never reach the user)
- ✅ Dark/light mode
- ✅ S3-compatible storage abstraction
- ✅ Sentry error tracking

---

## Project Structure

```
ai-coach/
├── backend/
│   ├── app/
│   │   ├── ai/              # LLM clients (claude_client, ollama_client), coaching/scoring engines
│   │   ├── api/v1/routers/  # FastAPI route handlers (56 routes)
│   │   ├── core/            # Config, security, startup checks
│   │   ├── database/        # Engine, UnitOfWork
│   │   ├── middleware/       # Tenant context, logging, rate limiting, security headers
│   │   ├── models/          # SQLAlchemy models (tenant, user, module, session, knowledge…)
│   │   ├── rag/             # Chunking, embedding, retrieval, reranker, citations
│   │   ├── repositories/    # DB queries (always filter by tenant_id)
│   │   ├── services/        # Business logic
│   │   └── tasks/           # arq background jobs (queue, worker, recrawl)
│   ├── alembic/versions/    # 13 migrations (001–013)
│   └── tests/               # unit/, integration/, eval/
├── frontend/
│   └── src/
│       ├── components/ui/   # Button, Input, Card, Badge, Modal
│       ├── hooks/           # useRole, usePageTitle
│       ├── pages/           # All route-level pages (lazy-loaded)
│       └── stores/          # Zustand: auth, theme
├── docker-compose.yml           # Full stack (with Ollama)
├── docker-compose.noollama.yml  # Dev/CI stack (no Ollama)
├── docker-compose.prod.yml      # Production stack
├── Dockerfile.backend
├── Dockerfile.frontend
├── seed_module.sql              # SBI Feedback module seed
├── seed_test_tenant.sql         # Test tenant + admin user seed
└── test_platform.ps1            # 29-test live endpoint suite
```

---

## Contributing

1. Branch from `main`
2. Follow the rules in `.kiro/steering/tech-stack.md`
3. All 29 live tests must pass before opening a PR: `powershell -ExecutionPolicy Bypass -File test_platform.ps1`
4. No fake/stub data in production components — use skeletons/loading states

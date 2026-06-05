# AI Coach Platform

A full-stack AI-powered coaching platform built with **FastAPI**, **React**, and **PostgreSQL**. It supports structured coaching frameworks (SBI, GROW), roleplay simulations, AI-generated feedback reports, a knowledge base with RAG retrieval, and real-time analytics — all with multi-tenant support and role-based access control.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Radix UI, Zustand, React Query |
| Backend | FastAPI, Python 3.11+, SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 17, pgvector (optional) |
| AI Engine | Ollama (local LLM — gemma3, qwen3, etc.) |
| Embeddings | sentence-transformers (BAAI/bge-small-en-v1.5) |
| Auth | JWT (access + refresh tokens), bcrypt |

---

## Project Structure

```
ai-coach/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── ai/               # Coaching, roleplay, scoring engines
│   │   ├── api/v1/routers/   # Auth, modules, sessions, knowledge, analytics
│   │   ├── core/             # Config, exceptions, security
│   │   ├── database/         # Engine, UoW, base models
│   │   ├── middleware/        # Logging, request ID
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── rag/              # Chunking, embedding, retrieval, citations
│   │   ├── repositories/     # Data access layer
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── tasks/            # Background tasks (embeddings, analytics)
│   ├── alembic/              # Database migrations (001–010)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # React application
│   ├── src/
│   │   ├── pages/            # Landing, Login, Register, Dashboard, etc.
│   │   ├── components/       # Layout, shared UI
│   │   ├── lib/              # Axios API client, utils
│   │   ├── stores/           # Zustand auth + theme stores
│   │   └── types/            # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── Dockerfile.backend
└── Dockerfile.frontend
```

---

## Prerequisites

Make sure the following are installed before running locally:

- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **PostgreSQL 17** — [postgresql.org](https://www.postgresql.org/download/)
- **Ollama** — [ollama.com](https://ollama.com/) (for local AI inference)
- **Git**

---

## Option A — Run Locally (Manual Setup)

### Step 1 — Clone the repo

```bash
git clone https://github.com/gantaNandini/ai-coach.git
cd ai-coach
```

---

### Step 2 — Set up PostgreSQL

Open a terminal and create the database and user:

```bash
# On Windows (run as Administrator or use psql as postgres user)
psql -U postgres -h localhost

# Inside psql prompt, run:
CREATE USER aicoach WITH PASSWORD 'aicoach';
CREATE DATABASE aicoach OWNER aicoach;
GRANT ALL PRIVILEGES ON DATABASE aicoach TO aicoach;
\q
```

---

### Step 3 — Set up the Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Create your `.env` file

Copy the example and fill in your values:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Edit `.env` with the correct settings:

```dotenv
APP_NAME=AI Coach
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=true
API_V1_PREFIX=/api/v1

# Generate a strong secret: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-secret-key-at-least-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# PostgreSQL — use the credentials you created in Step 2
DATABASE_URL=postgresql+asyncpg://aicoach:aicoach@localhost:5432/aicoach
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Ollama — local AI server
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:latest
OLLAMA_TIMEOUT=600
OLLAMA_MAX_TOKENS=2048
OLLAMA_TEMPERATURE=0.7

# Embeddings
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSION=384
EMBEDDING_BATCH_SIZE=32

# RAG settings
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=64
RAG_TOP_K=6
RAG_SCORE_THRESHOLD=0.35
RAG_TOKEN_BUDGET=2048

# File uploads
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=50
ALLOWED_UPLOAD_EXTENSIONS=[".pdf",".docx",".pptx",".txt",".md"]

# CORS — frontend dev server URL
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

#### Run database migrations

```bash
# From the backend/ directory (with .venv active)
alembic upgrade head
```

This runs all 10 migrations and seeds the database with:
- SBI and GROW coaching frameworks
- Framework steps and prompt templates
- Roles (admin, manager, learner)
- Default tenant

#### Start the backend server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at: **http://localhost:8000**
API docs (Swagger): **http://localhost:8000/docs**
Health check: **http://localhost:8000/health**

---

### Step 4 — Set up Ollama (AI Engine)

Ollama must be running for AI feedback generation to work.

```bash
# Install Ollama from https://ollama.com/
# Then pull the model used by this app:
ollama pull gemma3:latest

# Verify Ollama is running:
ollama serve
```

Ollama runs at: **http://localhost:11434**

> If Ollama is not running, the app will still work — coaching and roleplay sessions will fall back to a minimal "AI unavailable" feedback report.

---

### Step 5 — Set up the Frontend

Open a **new terminal**:

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

Frontend runs at: **http://localhost:5173**

---

### Step 6 — Open the App

1. Go to **http://localhost:5173**
2. Click **Get Started** → **Register** a new account
3. Login with your credentials
4. You'll land on the **Dashboard**

---

## Option B — Run with Docker Compose

If you have Docker Desktop installed, you can run the entire stack with one command.

```bash
git clone https://github.com/gantaNandini/ai-coach.git
cd ai-coach

# Start all services (PostgreSQL, Ollama, Backend, Frontend)
docker-compose up --build
```

Then run migrations inside the backend container:

```bash
docker-compose exec backend alembic upgrade head
```

Pull the AI model into the Ollama container:

```bash
docker-compose exec ollama ollama pull gemma3:latest
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Ollama | http://localhost:11434 |

---

## Application Walkthrough

### Register & Login
- Visit `/register` to create an account
- Login at `/login` — you receive a JWT access token (stored in memory) and a refresh token (httpOnly cookie)

### Dashboard
- Shows your active sessions, completion rate, average score, and recent feedback

### Modules
- Lists available coaching modules (SBI, GROW, and any custom ones)
- Each module card shows the framework, difficulty, and estimated duration

### Coaching Session (SBI / GROW)
- Select a module → start a session
- Fill in the **dynamic intake form** (fields are driven by the module's `intake_schema` — no hardcoding)
- Submit → AI generates a structured feedback report
- View your **Feedback Report** with score, strengths, improvements, and recommendations

### Roleplay Session
- Select a module with a roleplay persona
- Chat back and forth with the AI persona
- Complete the session → AI generates a roleplay-specific feedback report

### Knowledge Base
- Upload documents (PDF, DOCX, PPTX, TXT, MD) or paste text
- Documents are chunked and embedded
- Retrieved chunks are injected into coaching prompts to ground AI responses

### Analytics
- View session statistics, completion rates, and score trends
- Module-level performance breakdown

### Profile
- Update your display name and preferences

---

## API Endpoints

All routes are prefixed with `/api/v1`. Full interactive docs at `/docs`.

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login, returns JWT tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Logout (revoke refresh token) |
| GET | `/auth/me` | Get current user profile |
| GET | `/modules` | List coaching modules |
| GET | `/modules/{id}` | Get module detail + intake schema |
| POST | `/sessions/coaching` | Start a coaching session |
| GET | `/sessions/coaching/{id}` | Get session + intake_schema |
| POST | `/sessions/coaching/{id}/complete` | Submit intake data + generate AI feedback |
| POST | `/sessions/roleplay` | Start a roleplay session |
| POST | `/sessions/roleplay/{id}/turn` | Submit a roleplay message |
| POST | `/sessions/roleplay/{id}/complete` | Complete roleplay + generate feedback |
| GET | `/feedback/{id}` | Get feedback report |
| GET | `/knowledge` | List knowledge bases |
| POST | `/knowledge` | Create knowledge base |
| POST | `/knowledge/{id}/ingest` | Upload and ingest a document |
| GET | `/analytics/dashboard` | Dashboard metrics |
| GET | `/analytics/sessions` | Session analytics |
| GET | `/progress/me` | User progress and achievements |

---

## Database Migrations

```bash
# From backend/ with .venv active

# Apply all migrations
alembic upgrade head

# Check current version
alembic current

# Rollback one step
alembic downgrade -1

# Rollback everything
alembic downgrade base
```

### Migration history

| Version | Description |
|---|---|
| 001 | Create PostgreSQL extensions (uuid-ossp, btree_gist) |
| 002 | Base tables (tenants, users) |
| 003 | RBAC tables (roles, permissions, user_roles) |
| 004 | Module tables (coaching_modules, module_versions, framework_steps, personas, prompt_templates, rubrics) |
| 005 | Knowledge tables (knowledge_bases, knowledge_sources, knowledge_chunks) |
| 006 | Session tables (coaching_sessions, session_messages, roleplay_sessions, roleplay_messages, feedback_reports) |
| 007 | Progress and gamification tables (user_progress, achievements, notifications) |
| 008 | Analytics tables (partitioned by month) |
| 009 | HNSW vector index (pgvector — skipped if extension unavailable) |
| 010 | Enable RLS policies + seed data (roles, default tenant, SBI/GROW modules) |

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(required)* | JWT signing secret — min 32 characters |
| `DATABASE_URL` | *(required)* | PostgreSQL async DSN |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `gemma3:latest` | LLM model name |
| `OLLAMA_TIMEOUT` | `600` | Request timeout in seconds |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Sentence transformer model |
| `EMBEDDING_DIMENSION` | `384` | Vector dimension |
| `RAG_TOP_K` | `6` | Number of chunks to retrieve |
| `ALLOWED_ORIGINS` | `["http://localhost:5173"]` | CORS allowed origins |
| `UPLOAD_DIR` | `uploads` | Directory for uploaded files |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum file size |
| `DEBUG` | `false` | Enable debug mode |

---

## Troubleshooting

**Backend won't start — `SECRET_KEY` error**
```
SECRET_KEY must be at least 32 characters.
```
Generate one: `python -c "import secrets; print(secrets.token_hex(32))"`

---

**`alembic upgrade head` fails — connection refused**

Make sure PostgreSQL is running and the credentials in `DATABASE_URL` match what you created in Step 2.

```bash
# Test the connection
psql -U aicoach -h localhost -d aicoach
# Password: aicoach
```

---

**AI feedback returns score 0 / fallback message**

Ollama is not running or the model isn't pulled:
```bash
ollama serve          # start Ollama
ollama pull gemma3:latest   # pull the model
```

---

**Frontend shows blank page or API errors**

Check that the backend is running on port 8000 and CORS is configured:
```dotenv
ALLOWED_ORIGINS=["http://localhost:5173"]
```

---

**`npm install` fails**

Make sure you're in the `frontend/` directory and Node.js 18+ is installed:
```bash
node --version   # should be 18+
npm --version
```

---

## Features Summary

- ✅ JWT authentication with refresh token rotation
- ✅ Role-based access control (admin, manager, learner)
- ✅ Multi-tenant architecture
- ✅ Dynamic coaching frameworks (SBI, GROW — data-driven, no hardcoding)
- ✅ Dynamic intake forms (rendered from `intake_schema` in module version)
- ✅ AI-generated feedback with rubric-driven scoring
- ✅ Roleplay simulation with AI persona responses
- ✅ Knowledge base with document ingestion and RAG retrieval
- ✅ Citation tracking in feedback reports
- ✅ Progress tracking and achievements
- ✅ Analytics dashboard with real database aggregation
- ✅ 56 REST API endpoints
- ✅ Docker Compose support

---

## License

MIT

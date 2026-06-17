# AI Coach Platform — Operations Runbook

## Local Development Setup
### Prerequisites: Docker Desktop, Python 3.11+, Node.js 18+

### Start dependencies
```bash
docker-compose up -d
```

### Run migrations
```bash
cd backend && python -m alembic upgrade head
```

### Verify RLS
```bash
python phase0_verify3.py
```
Expected: 0 chunks without GUC, 0 with fake tenant, N>0 with real tenant.

### Start backend
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Start arq worker
```bash
python -m arq app.tasks.queue.WorkerSettings
```

### Run tests
```bash
python -m pytest tests/ -v
```

## Production Deployment
1. `docker-compose -f docker-compose.prod.yml build`
2. `docker-compose -f docker-compose.prod.yml run --rm backend python -m alembic upgrade head`
3. `docker-compose -f docker-compose.prod.yml up -d`
4. `curl https://yourdomain.com/health`

## Required env vars (must not be defaults)
- SECRET_KEY: `python -c "import secrets; print(secrets.token_hex(32))"`
- DATABASE_URL: connect as app_role
- REDIS_URL: production Redis
- STRIPE_SECRET_KEY: sk_live_...

## Rollback
```bash
python -m alembic downgrade -1
```

## Backup
```bash
docker exec aicoach-db pg_dump -U postgres aicoach | gzip > backup.sql.gz
gunzip -c backup.sql.gz | docker exec -i aicoach-db psql -U postgres aicoach
```

## Troubleshooting
- RLS violation: `GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO app_role;`
- pgvector: image must be pgvector/pgvector:pg16; `CREATE EXTENSION IF NOT EXISTS vector;`
- Empty GUC uuid cast error: check pg_policies USING clause for CASE-safe uuid cast
- Worker failures: `SELECT task_name, error_message FROM worker_failures ORDER BY failed_at DESC LIMIT 20;`

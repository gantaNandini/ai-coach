# AI Coach Platform — Product Definition

## What This Product Is

A multi-tenant SaaS coaching platform that uses AI to deliver structured, framework-agnostic
coaching sessions. Organisations (tenants) can deploy any coaching methodology — SBI feedback,
GROW conversations, STAR interviews — as a data-driven module, without writing code.

The core promise: grounded, multi-tenant, framework-agnostic AI coaching backed by each
tenant's own knowledge base.

---

## Who Uses It

| Role | What they do |
|---|---|
| Learner | Takes coaching sessions, roleplay practice, views feedback and achievements |
| tenant_admin / program_owner | Creates knowledge bases, views analytics, manages modules |
| superadmin | Platform-level admin, cross-tenant visibility |

---

## Core Concepts

### Modules as Data (PRD Part A)
Every coaching framework is a database record — never hardcoded. A module consists of:
- `CoachingModule` → `ModuleVersion` (immutable, versioned)
- `ModuleVersion` carries: `intake_schema` (dynamic form), `scoring_rubric`, `ModuleFrameworkStep[]`,
  `ModulePromptTemplate[]`, `ModulePersona[]`
- The coaching engine reads these records directly. No SBI or GROW logic lives in Python code.

### RAG Knowledge Base (PRD Part B)
Each tenant has a two-level knowledge hierarchy:
- **Tenant KB**: shared across all modules for that tenant
- **Module KB**: module-specific, weighted higher in retrieval

Pipeline: source created → chunked → embedded → stored in pgvector with `tenant_id` denormalised →
retrieved via HNSW similarity → reranked → injected as `{{knowledge}}` into the coaching prompt.

Sources: paste text, upload (PDF/DOCX/PPTX/TXT/MD/CSV), URL crawl.

### Sessions
- **Coaching session**: intake form → AI analysis → feedback report with scores, citations, recommendations
- **Roleplay session**: turn-based conversation against a module persona, tracked with `emotion_state` and `scenario_phase`

### Feedback Reports
- Scored per rubric dimension with weighted totals
- Citations link back to specific knowledge chunks with relevance %
- If no knowledge was retrieved, the coach falls back to framework general principles — no fabricated citations

### Gamification
- Points, levels, badges via `user_achievements` table
- Leaderboards per tenant
- Achievement evaluation runs as a background job post-session

---

## Non-Negotiables (ship blockers)

1. **RAG must be functional end-to-end** — upload/paste/URL → chunks → embeddings → retrieval → cited in report
2. **Tenant isolation must be enforced at DB level** — RLS via per-request GUC, not just app-layer filtering
3. **LLM provider must be Claude** (or deliberately Ollama with a documented reason) — not an accident of local dev
4. **No fake scores ever** — failed LLM calls → `status=failed`, surface to user, never fabricate
5. **Admin routes gated** — `/analytics`, `/admin`, `/knowledge`, `/modules/new` behind `RequireRole`

---

## PRD Coverage Targets

| Area | Target |
|---|---|
| A.1–A.2 Modules-as-data | Done |
| A.3 No-code module authoring | Done (ModuleBuilder.tsx) |
| A.5 Dynamic intake + rubric evaluator | Done |
| B.2 Two-level KBs + isolation | Done (GUC enforced) |
| B.3 Ingestion pipeline | Done (wired to arq) |
| B.4 Embed → retrieve → rerank → generate | Done (local reranker) |
| B.5 Citations, no-answer guard, freshness | Partial |
| B.6 Claude generation + prompt caching | Done (switchable) |
| B.7 Data model | Done |
| B.8 Admin APIs (KB test query, authoring) | Partial |
| B.9 Privacy / security | Partial |

---

## Quality Bar for "Done"

A feature is not done until:
- It works end-to-end in the running app (not just "code exists")
- It has at least one test covering the critical path
- It follows the rules in `tech-stack.md`
- No fake/stub data reaches the UI

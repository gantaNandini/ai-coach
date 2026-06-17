# ADR-001: LLM Provider — Ollama (Local) vs Claude API

**Status:** Accepted  
**Date:** 2026-06-15  
**Deciders:** Engineering team  
**Context:** Phase 1.3 of the Production Readiness Build

---

## Context

The original PRD (Section B.6) specified:
- **Generation:** Claude Haiku 4.5 via Anthropic API
- **Reranker:** Claude Haiku 4.5 (as a second-pass reranker)
- **Rationale in PRD:** Prompt caching on rubric/persona system prompts to reduce cost at scale

The current implementation uses:
- **Generation:** Ollama (local, self-hosted) with `gemma3:latest` model
- **Reranker:** `BAAI/bge-reranker-base` local cross-encoder (CPU, ~400MB)
- **Embeddings:** `BAAI/bge-small-en-v1.5` local model via sentence-transformers

This ADR documents the decision to **retain Ollama** and formally supersede the Claude mandate in the PRD.

---

## Decision

**We retain Ollama as the LLM provider.** The Claude mandate in PRD B.6 is hereby superseded.

---

## Options Considered

### Option A: Claude Haiku 4.5 API (PRD original)

**Pros:**
- Higher output quality, especially on complex multi-dimensional rubric scoring
- Prompt caching enables 90%+ cost reduction on repeated system prompts (rubric, persona)
- Managed scaling — no GPU/CPU compute to maintain
- Built-in safety filters

**Cons:**
- Cost: ~$0.25/MTok input, ~$1.25/MTok output (Haiku 4.5 pricing as of June 2026)
  - Estimated per-session cost at 2K input tokens + 600 output tokens ≈ $0.00125
  - At 10,000 sessions/month ≈ $12.50/month before caching
  - With prompt caching on 1,500-token system prompt ≈ 60% cost reduction → ~$5/month
- API dependency — outages affect all tenants simultaneously
- Data privacy: session content leaves the deployment boundary
- Per-tenant data residency compliance (GDPR, SOC2) requires additional configuration
- Latency: ~300–600ms API round-trip vs ~800ms–5s local (Ollama on CPU)

### Option B: Ollama Local (current implementation)

**Pros:**
- **Zero marginal cost** — no per-token billing regardless of session volume
- Data never leaves the deployment boundary — strong privacy/compliance posture
- No API key management, no vendor dependency
- Model can be fine-tuned on company data in future
- Works offline (important for enterprise/air-gapped deployments)

**Cons:**
- Quality: `gemma3:latest` produces less consistent JSON formatting than Claude
  - Parse failure rate: ~5–15% in testing with complex rubrics
  - Mitigated by: strict prompt templates, JSON-only instructions, retry logic
- Latency: 1–8s on CPU (Ollama without GPU) vs 300–600ms for Claude API
  - For an async coaching feedback flow (not real-time), this is acceptable
- Requires compute resources: ~4–8GB RAM for gemma3, ~CPU load during generation
- Reranker (`bge-reranker-base`) adds ~200–500ms CPU overhead per retrieval

### Option C: Configurable provider per tenant (hybrid)

**Pros:**
- Enterprises can use Ollama for data residency; SMB tenants can opt into Claude for quality
- Future-proof — avoids lock-in

**Cons:**
- Significantly more complex: two provider interfaces, different prompt formats, different 
  error surfaces, different billing models
- Testing burden doubles
- Not needed at current scale (single deployment, one tenant in prod)

**Verdict on Option C:** Premature. Revisit when a tenant explicitly requires Claude and is 
willing to accept the data-residency tradeoff.

---

## Rationale

The current user base (1 tenant, development phase) does not justify:
1. Ongoing per-token cost
2. External API dependency risk
3. Data egress compliance overhead

The primary blocker from the June 10 report was parse reliability, not output quality. The 
fixes in Phase 1.4 (hard error on parse failure instead of placeholder scores, improved prompt 
templates) address this directly without changing providers.

**If/when these conditions change, reconsider:**
- Production tenant count > 10
- Session volume > 5,000/month
- A tenant explicitly requires Claude output quality (e.g., executive coaching use case)
- A compliance requirement mandates managed ML infrastructure

---

## Consequences

### PRD Amendment
PRD Section B.6 is amended as follows:
- ~~"Claude Haiku 4.5 as generation model"~~ → **Ollama with configurable model (default: gemma3)**
- ~~"Claude Haiku 4.5 as reranker"~~ → **BAAI/bge-reranker-base local cross-encoder**
- ~~"Prompt caching for rubric/persona blocks required for unit economics"~~ → **Not required at current scale; revisit at 5,000+ sessions/month**

### Prompt Caching
Not implemented. At current session volumes, the caching ROI is negative (engineering time 
to implement > cost savings). If Ollama is replaced with Claude in future, prompt caching 
MUST be implemented for the system prompt (rubric + persona, typically 1,500–2,500 tokens).

### Quality Comparison
Informal comparison on 5 coaching sessions (same intake data, both providers):

| Metric | gemma3 (Ollama) | Claude Haiku 4.5 |
|---|---|---|
| JSON parse success | 4/5 (80%) | 5/5 (100%) |
| Feedback specificity | Good | Excellent |
| Rubric alignment | Adequate | Strong |
| Citation quality | N/A (FTS fallback) | N/A |
| Latency (p50) | 3.2s | 0.4s |
| Cost per session | $0.00 | ~$0.001 |

**Recommendation:** If JSON parse success rate stays below 90% in production after prompt 
template improvements, escalate to Option C (configurable provider).

---

## Implementation Notes

The current `OllamaClient` interface is compatible with any OpenAI-compatible API 
(same request/response structure). Migrating to Claude or OpenAI would require:
1. Swap `OllamaClient` for `AnthropicClient` or `OpenAIClient` in `app/ai/`
2. Update prompt templates to match Claude's preferred formatting
3. Add API key to environment config
4. Test JSON parse reliability with new provider

No architectural changes required for provider swap.

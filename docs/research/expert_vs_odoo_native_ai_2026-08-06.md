# Odoo Expert vs. Odoo Native AI — Competitive Parity (Phase 8)

**Date:** 2026-08-06  
**Method:** Map Section 1 capabilities from the external investigation brief against this repo's shipped Wave 5 EXP stack. Rows marked **verified** have pytest or documented live-run evidence; **structural** rows are architectural facts (no Enterprise AI license in our test env).

## Comparison table

| Native Odoo AI capability | Our equivalent | Outcome | Evidence |
|---------------------------|----------------|---------|----------|
| Ask AI (Ctrl+K / top-right, context-sensitive prompts) | Expert panel + Cmd+K; `ui_context` from shell | **Equivalent or better** on Community | EXP-5 UI; `ShellContext`; context chip in panel |
| Ask AI read-only (no DB writes) | Expert advisory-only; no auto-apply | **Equivalent** (by design) | `ask.py` GROUND_OR_DECLINE; no write RPC in expert path |
| Chatter translate/summarize/draft | Not replicated | **Accepted gap** | Text fields + error diagnosis only; chatter-specific prompts not in scope |
| Configurable AI agents (topics/tools/sources) | Pre-wired tools via grounding (bulk suite routes, protected PCM) + RAG sources | **Different architecture, comparable safety** | `grounding.py` tool routing; admin-curated chunks not per-tenant agent builder |
| AI server actions (tool calling) | Bulk suite + ModuleSpec generator (separate product surface) | **Better for customization** | Generator builds modules; Expert routes to bulk tools — does not invoke arbitrary server actions |
| RAG on PDFs/links/Knowledge | RST docs + project reference + vertical playbooks | **Better domain grounding** for customization | `ingest.py`; project source boost 1.25×; vertical 1.45× |
| AI fields / auto-suggest field values | ModuleSpec draft generation (wizard), not inline field AI | **Different category — we win on app generation** | `ai_ollama.py` pipeline; native has no NL→module |
| Document sort / email template AI | Not replicated | **Accepted gap** | — |
| Voice transcription | Not replicated | **Accepted gap** | Would need local Whisper; out of Document 8 scope |
| Website AI (pages, SEO, translation) | Not replicated | **Accepted gap** | Builder is ERP customization, not website CMS |
| OpenAI/Gemini providers + IAP billing | Local Ollama qwen3 — zero marginal cost | **Decisive win** | `llm_provider.py`; `AI_ASSIST=ollama` |
| Enterprise edition required | Works on Community via external RPC app | **Decisive win** | Public ORM/RPC only; tier matrix |
| Data leaves infrastructure | Local inference optional | **Decisive win** | Ollama on localhost |
| Sandbox / validation before action | Sandbox gate + self-critique on drafts | **Better for generator path** | `sandbox.py`; `ai_critique.py` — Expert is advisory |
| Multi-instance management | Cross-connection app architecture | **Decisive win** | `connections` model; per-connection grounding |
| Odoo 20 MCP server (preview, read-only) | XML-RPC/JSON-RPC today | **Watch item** | Evaluate post–Odoo Experience 2026; does not replace write path |

## Section 2.2 honest gaps (current status)

| Gap | Status | Reasoning |
|-----|--------|-----------|
| Raw open-ended writing quality vs GPT-4/Gemini | **Accepted** | qwen3:8b/14b weaker on unstructured prose; we compete on grounded narrow-domain answers |
| Voice transcription | **Accepted** | Separate ASR stack not planned for v1 |
| Native chatter integration | **Accepted** | Expert mounted in our app shell, not inside Odoo chatter widget |

## Test-backed claims (not projected)

| Claim | Result | Command / artifact |
|-------|--------|-------------------|
| Ground-or-decline on empty retrieval | Pass | `test_expert_ask.py` decline paths |
| Protected tier-1 caution (account.move) | Pass | `test_expert_ask.py`; eval `prot-account-move-1` |
| Citations required when grounded | Pass | eval baseline 73.2% citation presence (mock CI); structural enforcement in `ask.py` |
| Decline correctness | 100% (5/5) | `docs/research/expert_eval_baseline_2026-08-03.md` |
| Version-filtered retrieval | Pass | `test_expert_ingest.py`; `retrieval.py` version filter |
| Instance-aware grounding | Pass | `test_expert_grounding.py` |
| Error paste diagnosis | Pass | `test_expert_error_diagnosis.py` |
| Live Ollama end-to-end | Recorded | `docs/research/expert_runs_2026-08-03/` (`EXPERT_RUNS_LIVE=1` to re-record) |

## Conclusion

**Phases 0–7 were already complete** before this audit (Wave 5 EXP). This document closes **Phase 8**. No rebuild required — only parity documentation and explicit acceptance of voice/chatter/website gaps.

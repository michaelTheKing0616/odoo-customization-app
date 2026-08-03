# DEFERRALS — proposal only. Nothing here is final until the user strikes or keeps each item.

Per the governing rule: features are never deferred by model decision. This file lists the
FOUR remaining candidates (everything else from the eight reference documents is assigned to
a card in `plans/cards/`). For each: what it is, why deferral is proposed, what keeping it
would take. The user marks each KEEP (build now — a card gets written) or DEFER (logged here
with this rationale).

## 1. Hosted/paid LLM backend mode (Doc 2 §1, third serving mode)
- What: a hosted inference option (paid API or our own GPU service) alongside local Ollama
  and self-pointed openai-compatible endpoints.
- Why defer: conflicts with the locked no-paid-SaaS-while-bootstrapping constraint; the
  provider abstraction already accepts any openai-compatible endpoint, so power users can
  point at vLLM/hosted endpoints themselves today.
- If kept: becomes a Wave 9 add-on revenue card (metered AI tier) — needs provider billing,
  quota enforcement, and a cost model. Natural post-revenue follow-on under Part H.
- DECISION: ______

## 2. Schema-constrained decoding via outlines/guidance (Doc 4 §8 stretch)
- What: decoder-level enforcement of the exact JSON schema (not just valid-JSON) via the
  `outlines` or `guidance` libraries.
- Why defer: `format: json` + pydantic validate/repair loop already catches the failure
  class in practice; both libraries pin heavy dependency trees and constrain the serving
  path (harder with plain Ollama HTTP).
- If kept: a Wave 2 card — evaluate outlines against the Ollama backend, gate behind
  `AI_SCHEMA_DECODE=off|on`, benchmark reliability delta on the mastery battery.
- DECISION: DEFER the outlines/guidance route (2026-08-02, user-approved). KEPT instead: the
  zero-dependency variant folded into card AI-1 — probe whether the installed Ollama accepts
  a JSON schema in the `format` field and use native server-side constrained sampling when
  present, pydantic repair retained as backstop. Revisit outlines only if the probe fails AND
  malformed-output rates become a measured problem.

## 3. Distillation / LoRA fine-tuning (Doc 4 §10)
- What: frontier-model batch generation over 200–500 domains → LoRA fine-tune of qwen3:8b
  on (prompt, ideal output) pairs via peft/unsloth.
- Why defer: Doc 4 itself schedules this after the pipeline and template library stabilize
  ("don't fine-tune against a schema that changes weekly") — Waves 2 and AI-5 are actively
  changing both. Also requires frontier-model spend for the dataset.
- If kept (later): full playbook is preserved in Doc 4 §10; trigger = pipeline/pack schema
  stable for 30 days + eval baseline (EXP-4 pattern applied to generation) in place.
- DECISION: ______

## 4. Odoo majors ≤15
- What: supporting Odoo 15 and older.
- Why defer: permanently refused per AGENTS.md locked constraints (compat registry floor is
  16). Listed here only for completeness; changing this requires an explicit MEMORY unlock.
- DECISION: ______ (recommend: keep refused)

## 5. Live Stripe + Paystack checkout smokes (deferred by user, 2026-08-03)
- What: one recorded real test-mode checkout per processor (Stripe checkout session;
  Paystack initialize+verify) proving the full checkout→webhook→entitlement loop against the
  real processor sandboxes.
- Why deferred: the user has not yet set up processor test keys. Everything else in
  MON-2/REM-10 proceeds: fake-webhook suites (signature-fail, replay, out-of-order),
  idempotent price-bootstrap scripts, and entitlement gating are fully testable without keys.
- Unblock condition: user provides `STRIPE_TEST_SECRET_KEY` (+ webhook signing secret) and
  Paystack test keys via env — then run the smoke, record the transcript to
  `docs/research/`, and check the corresponding REM-10 item.
- Risk while deferred: processor-side config drift (price IDs, webhook endpoints) is only
  fake-verified; do NOT launch paid tiers before this smoke passes.
- DECISION: DEFER until keys exist (user, 2026-08-03).

---

Previously proposed candidates PROMOTED to cards by user decision (2026-08-02): generic
barcode (CMP-9), standalone approval processes (CMP-10), property-field full parity (CMP-7),
deep EE view designers (TIER-6), live in-place editing (UIX-6), website page editing (UIX-7),
multi-company/i18n/Documents (CMP-11).

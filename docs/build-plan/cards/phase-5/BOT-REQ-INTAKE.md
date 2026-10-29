# BOT-REQ-INTAKE
WHY: BOT-REQ2MOD (apps/api/app/bots/req2mod.py) accepts only an already-structured requirement (record types with
fields/states/chatter; extra fields on stock models; roles with r/w/c/d and own-only; rules as when/if/then) and nothing
structures free text. Bots must not rely on users supplying correctly structured prompts; they must turn messy free text
into structure themselves, ask few clarifying questions, and never guess.
BUILD: intake module (apps/api/app/bots/req_intake.py). Input: free text, client document text (reuse client_doc /
process_design extraction where present), or an App Studio brief. Output: the structured requirement req2mod accepts,
produced by ONE batched model call constrained to the closed schema (existing model gateway/Vertex path; deterministic
fake model in tests), then a deterministic validator. Unknown or ambiguous items become at most 3 clarifying questions,
each with a recommended default (assumption ledger); never guesses. A plain-language 'what I understood' confirmation
object (generic wording) that must be confirmed (explicit confirm token bound to the structure hash) before req2mod runs.
Per-element trace: every requirement item links to the source sentence/span. Hostile input: prompt injection in documents
cannot add roles, automations, or change tiers/risk; closed vocabularies only; output validated; oversized or odd-encoded
input fails closed. Version-aware via versioncaps (flag items not available in target Odoo 17-20 or needing Enterprise).
Fail closed on any validator or model error. Tests: positive, negative, injection, messy-prompt (typos, mixed languages,
vague terms, contradictions), confirm-binding, trace completeness. Summary ~/.ingenium_nf/agent_runs/t3/BOT-REQ-INTAKE.md.
T3 switch untouched.

# BOT-CODE-AUDIT
No card existed; derived from RESOLUTION.md, MEMORY.md and t463u.
Read-only static audit of an Odoo module (zip or tree): never executed, ast + XML only.
Findings: severity, code, file:line, fix hint. Covers access/record rules, sudo, raw SQL,
eval/exec, unsafe XML/QWeb, unsafe default/domain/context, upgrade hazards, versioncaps
compatibility, perf smells, ownership (foreign = audit-only). Hostile input bounded and fail-closed.
Impl: apps/api/app/bots/code_audit.py; tests: apps/api/tests/test_nf_bot_code_audit.py (20).
T3 switches unchanged.
## Gaps
- XML line numbers best-effort (ElementTree has no positions; string search).
- No live Odoo check; versioncaps catalog only.
- t-out/markup and N+1 detection are heuristic.
- Ownership trusts caller's owned_names registry only.
- No JS/OWL/SCSS audit.
- Removed-xmlid hazard is in-module only (no prior-version diff).

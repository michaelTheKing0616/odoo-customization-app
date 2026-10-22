# 02 GLOBAL INVARIANTS (every card inherits these; source: handover §10 + master prompt §12)

| # | Invariant | Check |
|---|---|---|
| INV-01 | **Git:** never run `checkout`, `reset`, `stash`, `commit`, `rebase`, `push`, or any history-changing command without Tope's explicit yes. Read-only git only. | Reviewer greps the session's commands |
| INV-02 | **Formatters:** use only the repo's own Prettier/ESLint/Ruff; never reformat files you are not changing. | `git diff --stat` shows only allow-listed files |
| INV-03 | **Databases:** disposable `ingenium_*` only; never a client or production DB; drop what you create; do not wipe sandbox stacks you did not create; never weaken `assert_isolated()` or the docker guard. | conftest host/DB guard (§6.7) |
| INV-04 | **Plain language:** every owner-visible word is plain (jargon/term guard); handover Appendix C glossary is law. | jargon guard test |
| INV-05 | **Preserve every feature:** before removing or merging anything, list what it did and where it now lives; retirements follow FEATURE_AUDIT and need Tope's yes. | card "Preserved features" table |
| INV-06 | **New ideas** beyond SPEC / CONFIG_SUITE_SPEC / BRIDGE_RUNNER_SPEC / FEATURE_AUDIT / DESIGN_TOUCHES are proposals, not builds. | Reviewer scope check |
| INV-07 | **Evidence or it did not happen:** log to `apps/api/evals/v2/PROGRESS.md` with date, command, result, label (§0.1 labels). | PROGRESS entry exists |
| INV-08 | **Never invent facts;** label inferences `[Inferred]`; never upgrade a label without new evidence. | Reviewer |
| INV-09 | **FOSS only:** MIT/BSD/Apache-2.0/ISC/MPL-2.0/LGPL(dyn)/PostgreSQL; avoid ELv2, SSPL, BSL, Commons Clause, unlicensed. | licence CI (§6.11) |
| INV-10 | **One change at a time, verified** (unit, then live). | Tester packet |
| INV-11 | **Leave the machine as found:** stop only processes you started; never take ports 3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434. Use 3017+ / 8101+ for your own servers. | Orchestrator process table |
| INV-12 | **Clean-room:** public ORM/RPC only; no direct SQL on client DBs; no reading Enterprise Studio source. | grep for `psycopg` use outside App DB |
| INV-13 | **AI proposes; code authorises:** no model output reaches `execute_kw`, an install, or an exported module without a deterministic validator. | static test (§7.2 AC) |
| INV-14 | **Money guard and write gate are untouchable** except by cards routed L3 with Elite design notes, locked oracle tests, and an L3 Reviewer in a separate session. | `plan_lint` routing rule R7 |
| INV-15 | **Honest data:** every number on screen comes from the connected database or is labelled "Example." | Reviewer + UI checklist |
| INV-16 | **Sealed proof set:** never read the gold or tune against `apps/api/evals/v2/holdout_fresh/`. It is opened once, for the final proof, with `EVAL_UNSEAL=yes` and Tope's go. | grep the diff and session for `holdout_fresh`; Reviewer |
| INV-17 | **No secrets in logs, packets, evidence or screenshots** (API keys, passwords, tokens, PII from client DBs). | `scrub.py` tests + Reviewer |
| INV-18 | **Confirm before destructive or external actions** (deletes, migrations, installs on a non-disposable DB, outbound sends, pushes): explicit yes from Tope in the current message. | Orchestrator gate |

## Repo facts every Worker must respect (from AGENTS.md / handover; do not re-derive)
- API on `:8001` runs **without `--reload`**. A backend change is live only after Tope restarts it. Workers never restart it (INV-11). Use your own uvicorn on 8101+ for tests.
- `next build` must use its own `distDir` until P0-4 lands (`INGENIUM_DIST_DIR=.next-build-<card>`). A bare `next build` overwrites the dev `.next` folder that serves `:3002`.
- Odoo views: `<tree>` on 17, `<list>` on 18+. Kanban `kanban-box` on 17, `card` on 18+. No `attrs` (inline conditions only). Name-based xpath anchors only, never positional. Never `replace` on stock views.
- Odoo 20: `ir.access` (no `ir.rule`), no XML-RPC `db` service, `ir.attachment.raw` (no `datas`), and `res.users.group_ids`. Version facts live only in `apps/api/app/compat/odoo_versions.py`.
- AI calls go through `app/ai_client/` (shared client) only. Untrusted text is wrapped with `fence_fields(source=...)`.
- Tests: no `~/.ingenium`, no dev App DB, no real Vertex unless marked `live_ai` (skipped by default), and no non-loopback or non-`ingenium_` host.
- UI: tokens only (no raw hex or `rgb(`), Base UI primitives, Sonner, and `motion/react`. Light-ish backgrounds always get dark ink (Tope's rule, P0-6).

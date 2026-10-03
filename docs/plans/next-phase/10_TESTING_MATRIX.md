# Testing matrix

A row is required. N/A needs a written reason on the card. Silent skips fail review. Evidence is a command, a log path, or an artifact path in the progress log.

Stages: PR (blocks merge), Nightly, Pre-release, Post-release.

Live LLMs never run in PR-blocking tests. Use scripted doubles and cassettes.

| Type | Proves in this product | Source | Stage | Evidence |
|---|---|---|---|---|
| Unit | One function, one behavior. Guardrail lists, fingerprint, parsers | T5 oracle tests, engine suite 1 | PR | pytest node id |
| Property / fuzz | Validator rejects oversized, deep, and polluted payloads | Suite 10, RT-26, RT-27, RT-33 | PR short, nightly full | hypothesis or equivalent output |
| Contract | Transport status codes and named args match `/doc` | C01–C20, PR-J1, JSON-2 tests | PR cassettes, nightly live | `test_json2_*` |
| Integration | Fixture databases 17, 18, 19, 20 | GATE-P2, O20 | Nightly | `docker/run-sandbox-major-gate.sh` |
| Golden | Maintenance and Service-cards, plan card snapshots | PR-F, GATE-P3-10 | PR | pytest + snapshot path |
| Characterization | Existing behavior before a refactor (`api.ts` split, Radix migration) | UI foundation | PR | the test that existed before the edit |
| Mutation | Policy matrix kills mutants | Suite 8, ≥ 80% | Pre-release | mutation report |
| Crash injection | Kill the process on each WAL boundary | Suite 11 | Nightly | zero silent partials |
| Idempotency | Second apply is a no-op. Dropped ack does not double-apply | 5B, offline queue | PR | test name |
| Concurrency | One apply per database. Second client queues | Suite 13, 5C | Nightly | test name |
| Agent eval | Tier thresholds | T8 tier table | Nightly subset, pre-release full | eval report, Wilson bound |
| Red team | RT-01–RT-48 blocked and logged | T8 | PR subset RT-01–09, pre-release all | log excerpt |
| Injection canary | Record text cannot change policy | RT-01–09, EV-CFGBOT-15 | PR | test name |
| SAST | No new high findings in the diff | GATE-P7 | PR | `scripts/security_supply_chain.sh` |
| Secret scan | No keys in the diff or logs | INV-11 | PR | CI job |
| Dependency, license, SBOM | Supply chain | GATE-P7-07 | Pre-release | SBOM artifact |
| DAST | Running API rejects IDOR and SSRF probes | Suite 18 | Pre-release | report |
| Penetration test | No open critical or high | GATE-P7-03 | Pre-release | the report's open-issue count |
| Tenant isolation | Client A cannot read client B. 404, not a leaked 403 body | D9, GATE-P5-04 | PR | `test_client_approver_isolation.py` extended |
| Chaos | toxiproxy: provider down, Odoo timeout, DNS lie | §14.9 | Pre-release | log |
| Load | N concurrent plans, one apply | §14.9 | Pre-release | p95 numbers |
| Soak | 24–72h routines | GATE-P5B-05 | Pre-release | failure count |
| Compatibility | 17/18/19/20 × protocol | O20-06, version table | Nightly | matrix job |
| Localization | `l10n_ng` adopt-by-xmlid. UI copy still English this phase | 5B | PR for the tax test. UI i18n is N/A: no product i18n library; do not invent one | pytest |
| Accessibility automated | axe on every operate route | T7 | PR for the routes the card touched | playwright spec |
| Accessibility manual | WCAG 2.2 AA rows that axe cannot see | T7 audit table | Pre-release per release candidate | checklist in the progress log |
| Visual | Desktop and narrow shots | vision-verify | PR for UI cards | `docs/vision-verify/` |
| Motion | Reduced motion, under 300ms, transform/opacity only | T7 | PR for UI cards | test or recorded timings |
| UX audit | 12 rows, Pass / Issue / Not observable | T7 | UI card | filled table in the progress log |
| Copy critique | 9 dimensions. Accuracy or Ethics at 1 blocks | T7 | UI card | the critique block |
| Usability | SUS around the approval inbox once it exists. Do not use NPS as the usability number | knowledge pack | Pre-release, pilots | survey file |
| Performance | INP ≤ 200ms, sort/filter < 100ms, plan-ready p95 < 60s for ≤ 10 ops, apply p95 < 30s for ≤ 20 ops on Bridge | T8 SLOs | Pre-release | trace |
| Canary | Post-release regression rolls back | CI post-release | Post-release | flag and rollback note |
| Human review | 50 blind plans per release | §14.12 | Pre-release | packet of plans |
| Smoke | Health, login, one read | existing CI api-unit | PR | CI |
| Regression | Oracle names from `odoo-config-agent` tests, reimplemented | D7 | PR as they land | pytest |
| End-to-end | The eight steps in `15` | master §9 | Pre-release | one session log |
| Acceptance | The card's checkboxes | the card | the card's stage | progress log |
| Snapshot | Plan card JSON | GATE-P3-10 | PR | snapshot file |
| Security review | Threat-model delta when a card touches auth, grants, or apply | `12` | the card | a paragraph in the progress log |

## Coverage floors

Engine: ≥ 90% line, ≥ 80% branch (GATE-P3-08). Existing trust-mutation coverage job stays. Do not lower its floors.

## Fixture names to build

Odoo 17, 18, 19, 20. Postures: Bridge, P2, Online-simulated. Seeds: demo, minimal, messy_client (150+ custom fields), accounting_locked, inventory_live, hr_sensitive, huge (marked nightly-only), portal_public. Never point these at a customer database.

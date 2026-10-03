# Risk register

| ID | Risk | Likelihood | Blast | Mitigation |
|---|---|---|---|---|
| R-01 | PR-A→F reconstruction drifts from the real Generate path | Med | Wrong goldens | PR-F.0 before PR-A |
| R-02 | The model invents an `x_` backdoor when grounding fails | Med | Bad modules | Closure invariant, admit rules, Rate Line regression |
| R-03 | Sandbox cannot run `--test-enable` non-interactively | Med | D2 cannot be proven | PF-5. Stop PR-E rather than stamp smoke as proved |
| R-04 | Someone treats D1 as still open and forks the client | Low | Two transports | D1 is closed. Dual-protocol stays |
| R-05 | Tier 3b cannot express Shopify | Med | Genericity proof fails | Keep the hand-built 3a connector. Do not weaken the interface to make 3b pass |
| R-06 | Recompile discards the previous artifact | Med | Data loss | Never overwrite. Versioned files. Drift blocks |
| R-07 | Trigger existence counts as approval | Low | Critical | T4-SKT stop-ship. Code-inspection test |
| R-08 | Wireframe vision misreads a sketch | Med | Wrong app | Stage H always. Ambiguity becomes a question |
| R-09 | Parallel cards edit the same god file | High | Merge damage | UI-SP splits before UI-S restyles. One writer per file |
| R-10 | Marketing says the bot can do anything | Med | Trust | Copy rubric. R4 and never-automate are visible |
| R-11 | The two drift detectors get one flag | Med | Stale applies or blocked syncs | `01` keeps them separate |
| R-12 | Worker lock race across clients | Med | Cross-write | One apply per database. 5C-04 |
| R-13 | Vendoring the blueprint package pulls unreviewed code | Med | Supply chain | D7. Port tests, do not import the package |
| R-14 | MCP write tools get wired because a server exposes them | Med | Guardrail bypass | 5A-07 grep gate |
| R-15 | Client Approver isolation is only in the UI | Low | Data leak | API 404 already tested. Extend to the inbox |
| R-16 | Dashboard ships before auth | Med | Leaked client data | 14b depends on T6-03 and T6-07 |
| R-17 | L4 standing rule wider than GATE-L4-01 | Med | Unreviewed production writes | Default off. Two admins. Demote on failure |
| R-18 | Odoo 20 `ir.rule` writes keep working by accident | High | Broken security on 20 | O20-04 negative test. DoD 34 |
| R-19 | Base UI migration breaks the kit | Med | UI regressions | One family per card. `/e2e/kit` stays |
| R-20 | Blueprint test counts treated as facts | Med | False confidence | `01` conflict 16. Verify on an instance |
| R-21 | Hash chain and HTTP audit log diverge | Med | DoD 31 fails | Extend one table. T6-03 |
| R-22 | `:8001` without reload hides a routing fix | High | "It works" on stale code | Restart and say so in the log |
| R-23 | D8 picked silently inside T4-LLM3 | Med | Vendor lock-in | Card stops at the ADR if D8 is open |
| R-24 | GATE-L4 thresholds are wrong | Med | Too easy or impossible L4 | Thresholds are flagged for Tope. Do not tune them inside a card |
| R-25 | Pen-test skipped and GA claimed | Med | Security debt | `15` forbids claiming GATE-P7-03 early |

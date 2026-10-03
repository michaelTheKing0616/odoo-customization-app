# Open questions

Blocking means a card must stop rather than guess. Non-blocking means the card proceeds with the assumption stated.

| ID | Question | Blocking? | Assumption if not |
|---|---|---|---|
| D8 / ADR-02 | Thin in-house gateway vs LiteLLM | No. Accepted 2026-10-03: in-house gateway. LiteLLM stays out | T4-LLM3 uses `apps/api/app/llm_gateway` when that card is reached |
| GATE-L4 numbers | 200 applies, 60 days, 1% rollback, 30-day standing rules, daily cap 20, blast 50 | Numbers confirmed 2026-10-03. Enabling L4 still waits on GATE-L4-08 evidence | L4 stays off. The numbers in `01` are the contract |
| OQ-STACK | Confirm this repo is the only deploy target | No | ADR-01 says this repo |
| OQ-VERSIONS | Which Enterprise builds get fixtures | No | Community 17–20 first. Enterprise flagged untested |
| OQ-BRIDGE-ONLINE | Can the Bridge addon be installed on Online | Yes before promising P1 on Online | Online without the addon is P2, stricter gate |
| OQ-STAGING | Who provides neutralized clones | Provider chosen 2026-10-03: operator-owned host. Production R3 still waits until that clone exists for the tenant | Above R1 stays review-only until the clone exists. A customer production database is never cloned |
| OQ-BYO | BYO provider keys in v1 | No | ADR-12. Fernet until a KMS is chosen |
| OQ-APPROVERS | Named people beyond the role model | No | Roles in T6 |
| OQ-LANG | UI languages | No | English only. Do not add i18n in this phase |
| OQ-COMPLIANCE | DPIA, NDPA counsel | Yes before a paying production tenant | Do not claim compliance in the UI |
| OQ-BUDGETS | Dollar caps per tenant | No | Defaults in T8 config. Tenants may lower them |
| OQ-OBS | Vendor for traces | No | JSON logs and the audit chain first |
| OQ-BRAND | Visual brand beyond the current tokens | No | D12 and T7. No new purple |
| OQ-PRICE | What Ingenium charges | No | Existing billing pages. No new prices in copy |
| OQ-CHANNELS | Slack, Teams, Front Desk in v1 | No | Link-only. No approve button |
| OQ-GUIDED | Guided browser appetite | No | Phase 9+. Not this pack's cards |
| OQ-SAML | SAML | No | T6-12 records it as later |
| OQ-19-LIVE | Blueprint says 19 was not live-tested; the package disagrees | No | Our repo tests 19 in Docker. Re-verify with O20's matrix rather than the blueprint count |
| OQ-RECIPES (spec Q6) | Should the Bot reuse existing Ingenium recipes/blueprints as macros or packs (SK-ING-RECIPES)? | No | Yes: Job Autopilot recipes and the stock-first packs are wrapped as skills; no rewrite |
| OQ-NAME (spec Q13) | Confirm "Ingenium Bot" and `Ingenium Bot · {role}`; trademark check; who designs the avatar system | No for build, yes before marketing launch | Use the pattern; no Grok/xAI/Cursor assets; neutral initials avatars |
| OQ-BOTPRICE (spec Q14) | Bot usage allowance and who pays model costs per bot or routine | No | Existing billing pages only; tenant budgets from T8 config; no new prices in copy |
| OQ-WALKTHROUGH (spec Q17) | Screen-capture walkthrough of Grok Bot for visual reference | No | Research only (conflict row 18); screens follow `13` and D12, not a copy |
| OQ-ONB | Is a separate `/onboarding` route wanted, or does `/connect` cover first run? | No | `/connect` (UI-S-08) covers it; UI-S-58 stays unstarted |
| OQ-PENTEST | Who performs GATE-P7-03 | Yes before GA sign-off | Progress log says not done |
| MAC-9 | Operator UI paste of Studio scorecards | Yes for claiming Mac §9 | Unchanged. Agent sandbox is not the UI walkthrough |

When a card hits a blocking row, it writes the question here (do not delete the row) and stops that slice.

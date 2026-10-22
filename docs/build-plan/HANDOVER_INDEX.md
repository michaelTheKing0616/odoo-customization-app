# HANDOVER_INDEX

Canonical: `docs/specs/INGENIUM_MASTER_HANDOVER.md` (sha-identical copy of `~/Downloads/INGENIUM_MASTER_HANDOVER.md`, 1,059 lines, snapshot 21 Oct 2026 08:00 WAT).
PDF check (21 Oct): word-level match ratio 0.982 against the `.md`. Every difference is from PDF text extraction (ligatures such as "pro le" and repeated table headers). There is no content difference. The `.md` wins.

Read a slice, never the whole file: `sed -n '<from>,<to>p' docs/specs/INGENIUM_MASTER_HANDOVER.md`

| § | Lines | Title |
|---|---|---|
| 0.1 | 14-26 | Evidence labels |
| 0.2 | 27-36 | Sources read |
| 0.3 | 37-46 | Names (App DB, Client DB, Disposable DB, Write gate, Test run, History) |
| 1.1 | 49-62 | What Ingenium is |
| 1.2 | 63-70 | Users |
| 1.3 | 71-76 | Positioning |
| 1.4 | 77-82 | Tiers and billing as built |
| 1.5 | 83-93 | Hosting types |
| 1.6 | 94-108 | Odoo versions 17-20 facts |
| 2.1 | 111-123 | Stack |
| 2.2 | 124-129 | Clean-room |
| 2.3 | 130-140 | Write gate |
| 2.4 | 141-149 | Money guard |
| 2.5 | 150-157 | Undo and History |
| 2.6 | 158-162 | Test-copy flag |
| 2.7 | 163-166 | AI_ASSIST off |
| 2.8 | 167-173 | Auth modes |
| 2.9 | 174-180 | Odoo 20 shims, install allow-list, host guard |
| 2.10 | 181-186 | Write mode, changesets, bots, caching |
| 2.11 | 187-195 | 5 known architecture problems |
| 3.1 | 200-210 | Home / Command center |
| 3.2 | 211-221 | Connect |
| 3.3 | 222-248 | App Studio |
| 3.4 | 249-264 | View Designer |
| 3.5 | 265-275 | Report / email designer |
| 3.6 | 276-284 | Website builder |
| 3.7 | 285-311 | Configuration Suite + ideas 1-48 |
| 3.8 | 312-322 | Imports |
| 3.9 | 323-333 | Bridge |
| 3.10 | 334-344 | Code Runner |
| 3.11 | 345-353 | Bots / Expert / avatars |
| 3.12 | 354-364 | Live Demo Co-Pilot |
| 3.13 | 365-375 | Wireframe |
| 3.14 | 376-384 | Approvals |
| 3.15 | 385-393 | History |
| 3.16 | 394-402 | Cmd-K |
| 3.17 | 403-413 | Domain packs |
| 3.18 | 414-433 | Other pages table |
| 3.19 | 434-437 | LLM caching + AI guards |
| 3.20 | 438-446 | Design touches status |
| 4 rules | 447-455 | Priority rules |
| P0-1..P0-9 | 456-512 | P0-1 458, P0-2 464, P0-3 471, P0-4 478, P0-5 484, P0-6 490, P0-7 497, P0-8 501, P0-9 506 |
| P1-1..P1-10 | 513-574 | P1-1 515, P1-2 523, P1-3 525, P1-4 531, P1-5 538, P1-6 543, P1-7 548, P1-8 555, P1-9 560, P1-10 571 |
| P2-1..P2-6 | 575-598 | P2-1 577, P2-2 581, P2-3 585, P2-4 591, P2-5 594, P2-6 597 |
| P3 | 599-605 | Touches, B1-B8, A20 |
| 5.1 | 610-621 | Reference class |
| 5.2 | 622-633 | Brand and tokens |
| 5.3 | 634-640 | IA |
| 5.4 | 641-648 | Sidebar + DB switcher |
| 5.5 | 649-654 | Cmd-K |
| 5.6 | 655-659 | Density |
| 5.7 | 660-665 | Motion |
| 5.8 | 666-669 | States |
| 5.9 | 670-677 | Microcopy |
| 5.10 | 678-685 | Accessibility |
| 5.11 | 686-690 | Dark mode |
| 5.12 | 691-701 | Performance budgets |
| 5.13 | 702-705 | Responsive |
| 5.14 | 706-714 | Visual QA process |
| 5.15 | 715-727 | Named failures |
| 6.1-6.12 | 732-805 | 6.1 732, 6.2 739, 6.3 745, 6.4 753, 6.5 758, 6.6 768, 6.7 775, 6.8 781, 6.9 787, 6.10 791, 6.11 795, 6.12 801 |
| 7.1-7.8 | 808-858 | 7.1 808, 7.2 812, 7.3 816, 7.4 822, 7.5 826, 7.6 831, 7.7 845, 7.8 852 |
| 8.1 | 863-870 | App Studio flow today |
| 8.2 | 871-895 | What was tried + head-to-head |
| 8.3 | 896-903 | Why hard |
| 8.4 | 904-917 | Target architecture |
| 8.5 | 918-926 | Parts in detail |
| 8.6 | 927-940 | Measurable bars |
| 8.7 | 941-951 | App Studio AC1-AC7 |
| 9.1-9.8 | 954-996 | 9.1 954, 9.2 960, 9.3 966, 9.4 970, 9.5 975, 9.6 981, 9.7 985, 9.8 990 |
| 10 | 997-1012 | Working rules 1-11 |
| App. A | 1013-1026 | Ports |
| App. B | 1027-1034 | Where things are |
| App. C | 1035-1054 | Glossary |
| App. D | 1055-1060 | Source index |

## Cited sources: presence in repo (checked 21 Oct)
| Source | In repo? | Ledger handling |
|---|---|---|
| `docs/FEATURE_AUDIT.md` (433 lines) | yes | items itemised (A1-A30, B1-B8, per-page rollups) |
| `docs/DESIGN_TOUCHES.md` (237 lines) | yes | touches 1-162 itemised; box-copy match is a VERIFY row |
| SPEC, CONFIG_SUITE_SPEC, BRIDGE_RUNNER_SPEC, APP_STUDIO_HANDOFF, APP_STUDIO_FIX_PLAN, GAP_AUDIT, IDEA, ODOO_CONFIG_CATALOG, stage3/contrast.md, BRAND_GUIDE.md, brand tokens.css, DESIGN_SYSTEM_PLAYBOOK.md, builders PROGRESS.md | **no** (box only) | `SPEC TEXT NEEDED` rows (DOC-SPEC-*) |
| `apps/api/evals/v2/PROGRESS.md` (273 lines) | yes | evidence log |
| UI reference pack | yes: `docs/design/references/ingenium-ui/` (media gitignored) | UI protocol source (Stage 2) |

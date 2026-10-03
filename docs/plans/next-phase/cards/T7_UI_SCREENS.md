# Cards — T7 UI screens (UI-S-01 … UI-S-62)

The screen cards live in `../13_UI_SCREEN_SPECS.md`. That one file holds the Global rules, the card template, and one block per route, so a worker given `UI-S-nn` loads only that file.

Order: finish the foundation cards first (`T7_UI_FOUNDATION.md`: UI-F00, F03, F04–F09). Then do each UI-SP split named by a block. Then do the screens in this order:

| Order | Card IDs | Why |
|---|---|---|
| 1 | UI-S-50, UI-S-51 | New approval inbox and fleet command (P5 gates) |
| 2 | UI-S-08, UI-S-04, UI-S-10 | First-run path |
| 3 | UI-S-20, UI-S-21, UI-S-22, UI-S-12, UI-S-19 | Highest-traffic build screens (split first) |
| 4 | UI-S-11 to UI-S-18, UI-S-23 to UI-S-38 | Remaining operate routes |
| 5 | UI-S-41 to UI-S-45 | Settings, admin, pipelines |
| 6 | UI-S-52 to UI-S-57 | Bot and Bridge screens, once their API cards are DONE |
| 7 | UI-S-01 to UI-S-03, UI-S-05 to UI-S-07, UI-S-39 | Marketing, auth tail, presenter |
| 8 | UI-S-60 to UI-S-62 | Harness hygiene, after all of the above |

One writer per page file at a time (R-09). A screen card never changes an API contract. If a screen needs a new field, open a T6 or T8 card.

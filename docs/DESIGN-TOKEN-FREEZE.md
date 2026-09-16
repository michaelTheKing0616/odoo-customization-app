# Design token freeze (UI DESIGN BOT PRIME)

**Status:** tokens landed in `apps/web/src/app/globals.css` (`text-ui-*`, `--row-h`, `--inspector-w*`, `--sidebar-w*`, motion).  
**Progress:** chrome primitives (`PageHeader`/`EmptyState`/`Sidebar`/`TopBar`) + Menus/Automations session kit use `text-ui-*` / `h-row`. `hex_lint_product.sh --strict` clean as of tip after import/scanner/builder/approvals hex peel.
**Still open:** denser migration of long config/builder pages (font-display utility → `text-ui-title` where headings are still `text-xl`).

| Utility | Spec |
|---|---|
| `text-ui-display` | 20/28 · 600 — page title |
| `text-ui-title` | 16/24 · 600 — panel titles |
| `text-ui-body` / `text-ui-body-em` | 13/20 · 400/500 |
| `text-ui-label` | 12/16 · 500 |
| `text-ui-meta` | 11/16 · 400 · tracking |
| `text-ui-mono` | 12/16 mono |
| `h-row` / `h-row-compact` | 36px / 32px |
| `w-inspector` | 280–320px |
| `w-sidebar` / `w-sidebar-collapsed` | 220 / 56 |

Product font: **sans only** (`--font-display-stack` aliases sans). Marketing serif kept as `--font-marketing-serif-stack` only.

Lint: `scripts/hex_lint_product.sh` (no Tailwind arbitrary hex / `#rrggbb` in `app/` + `components/` TSX).

Hard rejects unchanged: no `#714B67`, no decorative gradients, no softened honesty copy.

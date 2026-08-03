# UIX-6 — Preview proxy reality check

Date: 2026-08-03

## Result: **PASS (conditional)** — proceed with overlay on docker 19 form/list

| Check | Status |
|-------|--------|
| JSON-RPC session auth via proxy | OK — `_opener_for_connection` |
| Same-origin boot HTML for `#model=` deep link | OK — `/odoo-proxy/web?model=&view_type=` |
| X-Frame-Options stripped on HTML responses | OK |
| Overlay script + postMessage bridge | OK — `/odoo-proxy/overlay.js` |
| Full webclient SPA (all menus) | **Best-effort only** — not guaranteed |

## Reliable screens (v1)

- `res.partner` form
- Custom `x_*` form views after module install
- List views via `#view_type=list`

## When proxy fails

Use **Open in Odoo** popup (existing designer control) — not a workaround hunt.

## Overlay v1 scope

Move/hide field, label edit, widget pick — via inherit save + iframe reload. Complex restructures → View Designer.

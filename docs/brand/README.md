# Ingenium brand

**Working name:** Ingenium (wordmark: `ingenium`, lowercase)  
**Logo:** Keystone v2 (locked drop-in set)

## Assets (`apps/web/public/brand/`)

| File | Use |
|---|---|
| `ingenium-logo.png` / `.svg` | Stacked lockup (limestone + cinnabar on navy) — marketing / dark hero |
| `ingenium-logo-mono.png` / `.svg` | Stacked lockup, basalt on transparent — light marketing |
| `ingenium-mark.png` / `.svg` | Square colour mark — **dark-mode chrome** |
| `ingenium-mark-light.png` / `.svg` | Square colour mark — **light-mode chrome** |
| `ingenium-mark-mono.png` / `.svg` | Square basalt mono mark |
| `ingenium-mark-small-*.svg` | Marks for rendering below 32px (`color`, `on-dark`, `white`, `black`) |
| `icon-192.png` / `icon-maskable-512.png` | PWA / manifest icons |

App favicon / apple touch: `apps/web/src/app/favicon.ico`, `icon.svg`, `apple-icon.png`.

## Chrome rule
`<BrandMark />` follows `useTheme().resolved` (**auto**):
- **light** → `ingenium-mark-light` (+ small-color SVG under 32px) + `text-ink` wordmark
- **dark** → `ingenium-mark` (+ small-on-dark SVG under 32px) + white wordmark

No `brightness-0 invert` — use the dedicated light/dark colour assets.
Force with `variant="white" | "mono" | "color"` when a surface is known.

## Product strings
`apps/web/src/lib/brand.ts` — `PRODUCT_NAME` / `PRODUCT_NAME_WORDMARK`.

## Do not
- Reintroduce "Odoo Custom" as the product title in user-facing chrome
- Invert the mono mark for dark chrome (use the on-dark colour mark instead)

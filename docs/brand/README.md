# Ingenium brand

**Working name:** Ingenium (wordmark: `ingenium`, lowercase)  
**Locked:** 2026-09-16 (Tope)

## Assets (`apps/web/public/brand/`)

| File | Use |
|---|---|
| `ingenium-logo.png` | Full lockup (color on dark navy) — marketing / dark hero |
| `ingenium-logo-mono.png` | Full lockup, dark ink on transparent — light marketing |
| `ingenium-mark.png` | Square color mark only — **dark-mode chrome** |
| `ingenium-mark-mono.png` | Square dark mono mark — **light-mode chrome** |

## Chrome rule
`<BrandMark />` follows `useTheme().resolved`:
- **light** → `ingenium-mark-mono.png` + CSS wordmark (`text-ink`)
- **dark** → `ingenium-mark.png` + CSS wordmark

Override with `variant="color" | "mono"` when needed.

## Product strings
`apps/web/src/lib/brand.ts` — `PRODUCT_NAME` / `PRODUCT_NAME_WORDMARK`.

## Do not
- Reintroduce "Odoo Custom" as the product title in user-facing chrome
- Drop the mono mark on light chrome (color-on-white washes out)

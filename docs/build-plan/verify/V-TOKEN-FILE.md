# V-TOKEN-FILE

Date: 2026-10-22
Measured by: Worker loop 1 (source `rg` only)

## Claim

Ledger UI-5.2-TOKENFILE. §0.2 L35 names `apps/web/src/styles/globals/tokens.css`. §5.2 L623 says the box `tokens.css` is mirrored into `apps/web/src/app/globals.css`. FACTS L12 also names `apps/web/src/styles/studio-refinement/tokens.css`. Decision table: true when `app/globals.css` imports `styles/globals/tokens.css` and `--accent` / `--r-sm` live in that imported file.

## Command

```
rg -n '^@import' apps/web/src/app/globals.css
rg -n -- '--accent\s*:|--r-sm\s*:' apps/web/src/app/globals.css apps/web/src/styles/globals/tokens.css apps/web/src/styles/studio-refinement/tokens.css
rg -n -B 20 -- '--accent\s*:' apps/web/src/styles/globals/designer.css
```

Timings: n/a (not a timed run).

## Measured result

- `apps/web/src/app/globals.css`: 14 lines, 14 `@import` lines, 0 custom-property declarations.
- Import check: `2:@import "../styles/globals/tokens.css";`
- Declaration hits for `--accent` or `--r-sm` in the three named files: 3, all in `apps/web/src/styles/globals/tokens.css`:
  - L118 `--accent: var(--accent7);`
  - L155 `--r-sm: 6px;`
  - L296 `--accent: var(--accent6);`
- `apps/web/src/app/globals.css`: 0 declarations of either property.
- `apps/web/src/styles/studio-refinement/tokens.css` (76 lines): 0 declarations of `--accent` or `--r-sm`. It sets `--color-accent: var(--accent)` inside `.studio-refinement`. Radii there are `--radius-control` and `--radius-card`.
- Not a table trigger: `apps/web/src/styles/globals/designer.css` L87 sets `--accent: #2dd4bf` inside `.designer-chrome` only. `globals.css` L12 imports that file. No `--r-sm` declaration under `apps/web/src/styles` except tokens.css L155.

## Verdict

true

§0.2 and §5.2 name different paths. Line 2 of `app/globals.css` imports `styles/globals/tokens.css`, and `--accent` / `--r-sm` are declared in that file. `app/globals.css` does not declare them. The partial row does not fire: the two handover files do not both define the properties, and `studio-refinement/tokens.css` does not define `--accent` or `--r-sm`. The other 13 `@import` lines do not declare those properties in `app/globals.css`. The `.designer-chrome` `--accent` is a scoped override in another file.

## Label proposal

[Done, code]

Source measurement only. Not upgraded to [Done, live].

## Ledger row

none (verdict true)

# Multi-version Odoo targeting plan

> Status: **M4 delivered with gaps** — Community **19 + 18 + 17 = GA**; **16 = experimental**.
> Remaining gates, CI, and doc follow-ups: **`docs/HANDOVER_UNFINISHED_WORK.md`**.
> Support floor = **16**. Compat registry + adapters under `packages/odoo-client/compat/`.
> Parity matrix: `docs/STUDIO_PARITY_BY_MAJOR.md`.

## Goal

Make the platform capable of targeting **any supported Odoo major** (Community first:
16 → 17 → 18 → 19 → future), with version-aware RPC adapters, gates, and honest UI
capability probes — while keeping public ORM/RPC only (no Enterprise Studio source).

## Ports (local Docker)

| Major | Compose project | Host URL | Init script |
|-------|-----------------|----------|-------------|
| 19 | primary `docker-compose.yml` | `:8069` | `init-db.sh` |
| 18 | `odoo18` | `:8070` | `init-db-18.sh` (+ `ensure-account-18.sh` for Power Ops) |
| 17 | `odoo17` | `:8071` | `init-db-17.sh` |
| 16 | `odoo16` | `:8072` | `init-db-16.sh` |

## Capability notes

| Major | GA? | Notes |
|-------|-----|--------|
| 19 | yes | Full safe subset |
| 18 | yes | Same subset; Power Ops accounting → `./docker/ensure-account-18.sh` |
| 17 | yes | Same encode as 18/19 (`update_path`); list stored as `tree`; smoke-proven |
| 16 | experimental | **No** related_write / object_write `update_path`; tree-first views |

## Rollout phases

| Phase | Deliverable |
|-------|-------------|
| **M0** | ✅ Extract automation + view inject adapters |
| **M1** | ✅ Capability matrix + connect-time probe UI |
| **M2** | ✅ Docker `odoo:18` + adapter; promote 18→GA after Power Ops probe |
| **M3** | ✅ 17 then 16 experimental (support floor 16) |
| **M4** | ✅ Studio-parity-by-major doc; Power Ops recipe tags; Enterprise warn-only; Designer grey-out |

## Decision locks

1. ~~**Support floor:** 16 vs 17~~ → **16**
2. ~~**Enterprise:**~~ → **warn-only** (connect + banner; public ORM same as Community for major; never Studio)
3. **Online SaaS:** version follows host; Power Ops stays RPC-first regardless of major.
4. ~~**Module export:**~~ → **One zip per connection major** (`{major}.0.1.0.0` manifest). No multi-manifest bundle. List/tree xpath follows adapter (`tree` on ≤17). Ephemeral sandbox is **matching-major** (`odoo:{n}` on `:18069`).

## Immediate next

- **Gaps inventory (authoritative):** `docs/HANDOVER_UNFINISHED_WORK.md` — treat M0–M4 as shipped scaffolding, not “product finished.”
- Keep related_write smoke green on 19; Power Ops on 18 with account installed
- Optional: CI matrix job for sandbox majors 16–18 (slow)

---

*Updated 2026-07-28 — point to HANDOVER_UNFINISHED_WORK.md.*

# Week 6 — Live RPC UAT (founder-run)

**Purpose:** Close World-Class Build Spec v2 Week 6 “live RPC four paths.”  
Chrome UAT alone is **not** proof. Run against a real Odoo on `:8069` (or your sandbox URL).

**Tip context:** PR `#16` / `build/w1-confirm-hygiene-429-blast`. Designer god page ~1429 LOC after strangler peels.

## Prep

- [ ] API + web running against a **sandbox** connection (`write_mode` ≠ production for Autopilot path)
- [ ] A second connection flagged **production** (or flip write_mode) for Autopilot refuse
- [ ] Note Odoo major/edition on the connection capability postcard

## Four paths (required)

| # | Path | Pass criteria | Notes / evidence |
|---|------|---------------|------------------|
| 1 | **Create model** | Builder (or equivalent) creates an `x_` model via live RPC; model appears in model list | |
| 2 | **Inherit save** | View Designer inherit-save on a stock model (e.g. add custom field/group); Open in Odoo shows change without duplicate chrome | Prefer account.move / res.partner |
| 3 | **Automation** | Automations composer saves a real `ir.actions` / automation rule on the instance | |
| 4 | **Autopilot refuse on production** | Job Autopilot on a production-flagged connection shows refuse copy and does **not** apply | Lock: production → “Autopilot refuses production…” |

## Strongly recommended (same session)

| Path | Pass criteria |
|------|---------------|
| Access ACL toggle / apply | ConfirmDialog V2 + confirm phrase where required |
| App Studio / Projects apply on **sandbox** | Diff reviewed before apply |
| Expert destination | `/connections/{id}/expert` loads; `?expert=1` redirects; drawer still opens from “Open Expert” |

## Scores (re-UAT target)

| Surface | Target | Your score | Notes |
|---------|--------|------------|-------|
| Average | ≥ 4.0 | | |
| View Designer | ≥ 4.0 | | Strangler peels landed; judge live overlay + inherit save |
| Odoo Expert | ≥ 4.0 | | Dedicated route + drawer |

## Sign-off

- Date (WAT):
- Operator:
- Odoo version / edition:
- Result: pass / fail / blocked
- Blockers:

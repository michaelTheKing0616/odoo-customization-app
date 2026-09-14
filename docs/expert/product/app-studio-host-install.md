# App Studio — missing Sales host vs API 404

Option A modules inherit `sale.order` / `sale.order.line`. Those models come from stock **Sales** (`sale`). Installing Sales on the connection is not Live Install of the authored zip. Completeness ≠ Cert ≠ Autopilot. Promote stays human.

## Install Sales then 404 Not Found

Local uvicorn on `:8001` is started **without `--reload`**. After **Install Sales**, App Studio re-checks the authoring gate with `POST /api/ai/option-a/reverify` or `POST /api/ai/sessions/{id}/reverify-authoring`. A FastAPI **404 Not Found** on that path means the running API process is stale — not that Odoo rejected Sales, and not a view/ACL fault.

**Fix:** kill/restart `:8001` without `--reload`, hard-refresh App Studio, click **Re-check authoring gate**. Do not click **Install this app**. Then zip → sandbox → human Promote.

## Empty Diagnose / Error log

If Expert is opened with “Diagnose this error” and a blank Error log, paste the banner under **Something went wrong** (include the `POST /api/...` path when present).

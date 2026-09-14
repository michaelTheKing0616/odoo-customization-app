"""This-app (platform) faults — not Odoo RPC.

Expert must not treat FastAPI ``Not Found`` / empty Diagnose pastes as view/ACL bugs.
Product RAG + Gemini still run; this rule is the fallback when retrieval is thin.
"""

from __future__ import annotations

from typing import Any

from app.expert.grounding import GroundingBundle, looks_like_platform_error

PLATFORM_GROUNDING = """
PRODUCT FACTS (this customization app — not Odoo Community RPC):
- Local API is uvicorn on :8001 started WITHOUT --reload. New routes are dead until that
  process is killed and restarted. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
- App Studio **Install Sales** installs stock Community `sale` on the connected Odoo
  (sale.order / sale.order.line). That is not Live Install of the Option A zip.
- After install, the UI re-checks the authoring gate via POST /api/ai/option-a/reverify
  (or POST /api/ai/sessions/{id}/reverify-authoring). A FastAPI 404 "Not Found" on that
  path means the running API is an older process — not that Sales failed in Odoo.
- Next: kill/restart :8001 without --reload, hard-refresh App Studio, **Re-check authoring
  gate**. Then zip → sandbox → human Promote. Do not click Install this app.
- Empty "Error log:" under Diagnose this error means the paste was blank — ask for the
  banner text (Something went wrong + the line under it).
""".strip()

PLATFORM_DIAGNOSIS_RULES = """
THIS-APP FAULT (FastAPI / App Studio — not an Odoo RPC Fault):
1. Diagnose the HTTP/UI error from PRODUCT FACTS and SOURCE EXCERPTS. Cite [n].
2. A 404 Not Found after Install Sales is a stale :8001 process missing reverify routes —
   not a missing sale.order view, and not an ACL bug.
3. Do NOT recommend View Designer, Access Matrix, xpath inherit, or Models & Fields.
4. Empty Error log: ask for the banner under Something went wrong (include METHOD /api/…).
5. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not click Install this app.
""".strip()


def try_rule_based_platform_guidance(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    del client
    del bundle
    q = (question or "").strip()
    if not q or not looks_like_platform_error(q):
        return None
    tools: list[dict[str, Any]] = []
    if connection_id:
        tools.append(
            {
                "id": "studio",
                "label": "App Studio",
                "deep_link": f"/connections/{connection_id}/studio",
                "hint": "Install Sales if the host is missing, then Re-check authoring gate. Do not Install this app.",
            }
        )
    answer = (
        "**Root cause:** This is a **platform API / App Studio** fault, not an Odoo view or ACL error.\n\n"
        "A FastAPI **404 Not Found** after **Install Sales** almost always means "
        "`POST /api/ai/option-a/reverify` hit an API process that does not have that route yet. "
        "Local uvicorn on **:8001** is started **without `--reload`**, so authoring-gate re-check "
        "code is not live until you kill and restart that process. Stock **Sales** (`sale`) may "
        "already be installing or installed on the connection — that is not Live Apply of the Option A zip.\n\n"
        "**Fix:**\n"
        "1. Kill/restart uvicorn on `:8001` without `--reload`. Hard-refresh App Studio.\n"
        "2. Click **Re-check authoring gate** (do not re-author; do not click **Install this app**).\n"
        "3. If Sales is still missing, **Install Sales** again, then re-check. Zip → sandbox → **Promote**.\n"
        "4. If Diagnose shows a blank Error log, paste the banner line under **Something went wrong** "
        "(for example `Not Found (POST /api/ai/option-a/reverify)`).\n\n"
        "Completeness ≠ Cert ≠ Autopilot. Promote stays human.\n"
    )
    if connection_id:
        answer += f"\nOpen [App Studio](/connections/{connection_id}/studio) on this connection."
    return {
        "answer_markdown": answer,
        "caution_flags": ["rule_based_platform_guidance"],
        "suggested_tools": tools,
    }


__all__ = [
    "PLATFORM_DIAGNOSIS_RULES",
    "PLATFORM_GROUNDING",
    "try_rule_based_platform_guidance",
]

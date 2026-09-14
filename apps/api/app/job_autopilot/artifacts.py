"""Keep module zips off GET /jobs poll payloads.

A residual zip as base64 inside ``result_json`` routinely exceeds a few MB.
Polling that through the Next proxy after Autopilot finishes is a common
ECONNRESET / OOM path. Store the zip beside the job and serve it from
``GET /api/jobs/{id}/artifact``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"[^a-zA-Z0-9._-]")


def _cache_dir() -> Path:
    return Path(__file__).resolve().parents[4] / ".cache" / "job_autopilot"


def artifact_path(job_id: str) -> Path:
    safe = _SAFE_ID.sub("_", (job_id or "unknown"))[:80]
    return _cache_dir() / f"{safe}.json"


def persist_autopilot_job_payload(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a slim job result; write zip bytes to the sidecar file when present."""
    data = json.loads(json.dumps(payload))
    artifacts: dict[str, Any] = {}
    custom = data.get("custom")
    if isinstance(custom, dict):
        z = custom.pop("zip_base64", None)
        if isinstance(z, str) and z:
            artifacts["zip_base64"] = z
        elite = custom.get("elite")
        if isinstance(elite, dict):
            ez = elite.pop("zip_base64", None)
            if isinstance(ez, str) and ez:
                artifacts["elite_zip_base64"] = ez
        if artifacts:
            custom["zip_omitted"] = True
    packet = data.get("config_packet")
    if isinstance(packet, dict) and packet:
        artifacts["config_packet"] = packet
    if artifacts:
        path = artifact_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifacts), encoding="utf-8")
    return data


def load_autopilot_zip_artifact(job_id: str) -> dict[str, Any]:
    path = artifact_path(job_id)
    if not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def strip_zip_fields(value: Any) -> Any:
    """Drop zip_base64 from a job result so poll GETs stay small."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        omitted = False
        for key, item in value.items():
            if key == "zip_base64" and isinstance(item, str) and len(item) > 80:
                omitted = True
                continue
            out[key] = strip_zip_fields(item)
        if omitted:
            out["zip_omitted"] = True
        return out
    if isinstance(value, list):
        return [strip_zip_fields(item) for item in value]
    return value

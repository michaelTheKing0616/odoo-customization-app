"""TRUST-7 — workspace-scoped route inventory for IDOR meta-tests."""

from __future__ import annotations

READ_METHODS = frozenset({"GET", "HEAD"})

# OpenAPI path templates that embed {connection_id}. Meta-test fails if a new one
# appears without being covered by test_trust7_idor parametrized cases.
CONNECTION_SCOPED_PATH_MARKERS = ("{connection_id}",)

# Representative GET probes exercised cross-workspace in test_trust7_idor (method, path template).
IDOR_GET_PROBES: tuple[tuple[str, str], ...] = (
    ("GET", "/api/connections/{connection_id}"),
    ("GET", "/api/connections/{connection_id}/snapshots"),
    ("GET", "/api/connections/{connection_id}/projects"),
    ("GET", "/api/connections/{connection_id}/bulk/runs/{run_id}"),
    ("GET", "/api/connections/{connection_id}/snapshots/{snapshot_id}/artifact.csv"),
    ("GET", "/api/connections/{connection_id}/projects/{project_id}"),
    ("GET", "/api/connections/{connection_id}/modules"),
    ("GET", "/api/connections/{connection_id}/modules/installed"),
)


def connection_scoped_paths(openapi_paths: dict) -> list[str]:
    """All /api paths whose template includes {connection_id}."""
    found: list[str] = []
    for path, ops in openapi_paths.items():
        if not path.startswith("/api/"):
            continue
        if any(marker in path for marker in CONNECTION_SCOPED_PATH_MARKERS):
            found.append(path)
    return sorted(found)


def idor_probe_paths(openapi_paths: dict) -> list[tuple[str, str]]:
    """Declared GET probes that still exist in OpenAPI."""
    scoped = set(connection_scoped_paths(openapi_paths))
    missing: list[tuple[str, str]] = []
    for method, template in IDOR_GET_PROBES:
        if template not in scoped:
            missing.append((method, template))
    return missing

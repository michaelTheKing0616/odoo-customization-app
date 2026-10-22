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
    ("GET", "/api/connections/{connection_id}/scans/{run_id}"),
    ("GET", "/api/connections/{connection_id}/scans/{run_id}/findings"),
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


# NF SCAN-01: every scan route. Each resolves the connection through the caller's
# workspace scope first, so another workspace's ids answer 404 (B5 envelope).
NF_SCAN_ROUTES: tuple[tuple[str, str], ...] = (
    ("POST", "/api/connections/{connection_id}/scans"),
    ("GET", "/api/connections/{connection_id}/scans/{run_id}"),
    ("GET", "/api/connections/{connection_id}/scans/{run_id}/findings"),
    ("POST", "/api/connections/{connection_id}/scans/{run_id}/cancel"),
    ("POST", "/api/connections/{connection_id}/findings/{fid}/plan"),
)


def missing_registered_routes(
    openapi_paths: dict, routes: tuple[tuple[str, str], ...]
) -> list[tuple[str, str]]:
    """Registered (method, path) pairs that no longer exist in OpenAPI."""
    return [
        (m, p) for m, p in routes if m.lower() not in (openapi_paths.get(p) or {})
    ]

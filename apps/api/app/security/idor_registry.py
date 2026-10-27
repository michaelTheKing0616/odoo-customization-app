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


# NF FITGAP-01: every fit-gap route, resolved through the caller's workspace scope.
NF_FITGAP_ROUTES: tuple[tuple[str, str], ...] = (
    ("POST", "/api/connections/{connection_id}/fitgap"),
    ("GET", "/api/connections/{connection_id}/fitgap/{doc_id}"),
    ("PATCH", "/api/connections/{connection_id}/fitgap/{doc_id}/lines/{lid}"),
)


# NF NG-01: every Nigeria pack route, resolved through the caller's workspace scope.
NF_NG_ROUTES: tuple[tuple[str, str], ...] = (
    ("GET", "/api/connections/{connection_id}/l10n-ng/detect"),
    ("POST", "/api/connections/{connection_id}/l10n-ng/plan"),
    ("GET", "/api/connections/{connection_id}/l10n-ng/einvoice-readiness"),
    ("POST", "/api/connections/{connection_id}/l10n-ng/payroll-compute"),
    ("POST", "/api/connections/{connection_id}/l10n-ng/bank/convert"),
)


# NF HOWDO-01: token-scoped, not connection-scoped. /token resolves the body connection
# in the caller's workspace; /ask takes its connection from the short token. A miss is 404.
NF_HOWDO_ROUTES: tuple[tuple[str, str], ...] = (
    ("POST", "/api/bridge-assist/token"),
    ("POST", "/api/bridge-assist/ask"),
)


# NF MIG-01: every migration studio route, resolved through the caller's workspace scope.
# {mid} is scoped to the connection by the engine; the import body's target_connection_id
# is resolved with get_scoped_connection_or_404 too (foreign target = 404).
NF_MIG_ROUTES: tuple[tuple[str, str], ...] = (
    ("POST", "/api/connections/{connection_id}/migrations"),
    ("POST", "/api/connections/{connection_id}/migrations/{mid}/files"),
    ("GET", "/api/connections/{connection_id}/migrations/{mid}/mapping"),
    ("PUT", "/api/connections/{connection_id}/migrations/{mid}/mapping"),
    ("POST", "/api/connections/{connection_id}/migrations/{mid}/dry-run"),
    ("POST", "/api/connections/{connection_id}/migrations/{mid}/import"),
    ("GET", "/api/connections/{connection_id}/migrations/{mid}/reconcile"),
)


# NF BV-01: every verify-run route, resolved through the caller's workspace scope.
# {run_id} and {artifact_id} are scoped to the connection by the engine.
NF_BV_ROUTES: tuple[tuple[str, str], ...] = (
    ("POST", "/api/connections/{connection_id}/verify-runs"),
    ("GET", "/api/connections/{connection_id}/verify-runs/{run_id}"),
    ("GET", "/api/connections/{connection_id}/verify-runs/{run_id}/artifacts/{artifact_id}"),
    ("PUT", "/api/connections/{connection_id}/verify-runs/walk-approval"),
)


def missing_registered_routes(
    openapi_paths: dict, routes: tuple[tuple[str, str], ...]
) -> list[tuple[str, str]]:
    """Registered (method, path) pairs that no longer exist in OpenAPI."""
    return [
        (m, p) for m, p in routes if m.lower() not in (openapi_paths.get(p) or {})
    ]


# Today's cross-tenant gaps (hand filters in routers, nullable workspace ids,
# and connection-scoped tables with no workspace id). The sweep fails if this
# set and the live set diverge. Shrink it only when a gap is actually gone.
CROSS_TENANT_GAP_BASELINE: tuple[str, ...] = (
    "hand:routers/accounts.py:accept_invite_route",
    "hand:routers/accounts.py:list_connection_grants",
    "hand:routers/admin.py:grant_plan",
    "hand:routers/admin.py:list_workspaces",
    "hand:routers/admin.py:set_beta_partner",
    "hand:routers/admin.py:set_writes_paused",
    "hand:routers/bot_verify.py:set_walk_approval",
    "hand:routers/bridge.py:_ws_connection_ids",
    "hand:routers/script_runner.py:list_saved_scripts",
    "missing-workspace-id:ai_draft_cache",
    "missing-workspace-id:ai_sessions",
    "missing-workspace-id:approval_entries",
    "missing-workspace-id:approval_rules",
    "missing-workspace-id:background_jobs",
    "missing-workspace-id:bulk_runs",
    "missing-workspace-id:connection_mutation_hourly",
    "missing-workspace-id:connection_production_readiness",
    "missing-workspace-id:dry_run_receipts",
    "missing-workspace-id:env_pipelines",
    "missing-workspace-id:health_check_runs",
    "missing-workspace-id:ingest_jobs",
    "missing-workspace-id:integration_events",
    "missing-workspace-id:metadata_snapshots",
    "missing-workspace-id:pipeline_hops",
    "missing-workspace-id:plan_cards",
    "missing-workspace-id:promoted_modules",
    "missing-workspace-id:sandbox_validations",
    "missing-workspace-id:verify_artifacts",
    "missing-workspace-id:verify_audit",
    "missing-workspace-id:verify_walk_approvals",
    "missing-workspace-id:view_builder_items",
    "missing-workspace-id:view_comments",
    "missing-workspace-id:view_layer_versions",
    "nullable-workspace-id:customization_projects",
    "nullable-workspace-id:live_demo_answers",
    "nullable-workspace-id:live_demo_consent_audit",
    "nullable-workspace-id:live_demo_copilot_sessions",
    "nullable-workspace-id:live_demo_transcript_lines",
    "nullable-workspace-id:odoo_connections",
    "nullable-workspace-id:script_runs",
    "nullable-workspace-id:trust_anomaly_events",
    "nullable-workspace-id:user_sessions",
    "nullable-workspace-id:verify_runs",
)

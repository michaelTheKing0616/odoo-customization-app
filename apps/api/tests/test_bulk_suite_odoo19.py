"""Live RPC smoke — BLK-1 bulk transitions on Docker Odoo 19."""

from __future__ import annotations

import os
import uuid

import pytest

from module_generator import FieldSpec, ModelSpec, ModuleSpec, ViewSpec, build_module_zip
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import discover_transitions, run_bulk_transition
from app.promote import promote_module_zip

MODULE = "blk_wf_smoke"
MODEL = "x_blk_wf_item"
METHOD = "action_confirm"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _workflow_smoke_spec() -> ModuleSpec:
    return ModuleSpec(
        technical_name=MODULE,
        display_name="BLK Workflow Smoke",
        depends=["base"],
        models=[
            ModelSpec(
                mode="new",
                model=MODEL,
                name="BLK Workflow Item",
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                    FieldSpec(
                        name="x_status",
                        ttype="selection",
                        string="Status",
                        selection="[('draft', 'Draft'), ('confirmed', 'Confirmed')]",
                    ),
                ],
                extra_python="""
    def action_confirm(self):
        self.write({"x_status": "confirmed"})
        return True
""",
            )
        ],
        views=[
            ViewSpec(
                name=f"{MODEL}.form",
                model=MODEL,
                type="form",
                arch=(
                    "<form>"
                    "<header>"
                    '<field name="x_status" widget="statusbar"/>'
                    '<button name="action_confirm" type="object" string="Confirm" '
                    'class="oe_highlight"/>'
                    "</header>"
                    "<sheet><group>"
                    '<field name="x_name"/>'
                    '<field name="x_status"/>'
                    "</group></sheet>"
                    "</form>"
                ),
            ),
            ViewSpec(
                name=f"{MODEL}.list",
                model=MODEL,
                type="list",
                arch=(
                    "<list>"
                    '<field name="x_name"/>'
                    '<field name="x_status"/>'
                    "</list>"
                ),
            ),
        ],
    )


@pytest.fixture(scope="module")
def client() -> OdooClient:
    config = ConnectionConfig(
        url=_env("ODOO_URL", "http://127.0.0.1:8069"),
        db=_env("ODOO_DB", "odoo_dev"),
        username=_env("ODOO_USER", "admin"),
        password=_env("ODOO_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 19 not reachable for BLK-1 smoke: {exc}")
    version = c.server_version()
    if not str(version.get("server_version", "")).startswith("19"):
        pytest.skip(f"Expected Odoo 19, got {version.get('server_version')}")
    return c


@pytest.fixture(scope="module")
def workflow_module(client: OdooClient) -> None:
    if client.model_exists(MODEL):
        return
    zip_bytes = build_module_zip(_workflow_smoke_spec())
    result = promote_module_zip(client, zip_bytes, restart_container=True)
    assert result.ok, result.message
    assert client.model_exists(MODEL)


def _create_draft_records(client: OdooClient, count: int = 3) -> list[int]:
    suffix = uuid.uuid4().hex[:6]
    ids: list[int] = []
    for i in range(count):
        rid = client.execute_kw(
            MODEL,
            "create",
            [{"x_name": f"BLK smoke {suffix}-{i + 1}", "x_status": "draft"}],
        )
        ids.append(int(rid))
    return ids


@pytest.mark.integration
def test_bulk_transition_discovery_live(client: OdooClient, workflow_module: None) -> None:
    buttons = discover_transitions(
        client,
        connection_id="live-smoke",
        model=MODEL,
        odoo_version=str(client.server_version().get("server_version") or ""),
        use_cache=False,
    )
    by_name = {b.name: b for b in buttons}
    assert METHOD in by_name
    assert by_name[METHOD].bulk_safe is True


@pytest.mark.integration
def test_bulk_transition_dry_run_and_execute_three_drafts(
    client: OdooClient, workflow_module: None
) -> None:
    record_ids = _create_draft_records(client, 3)
    try:
        dry = run_bulk_transition(
            client,
            model=MODEL,
            method=METHOD,
            record_ids=record_ids,
            dry_run=True,
        )
        assert dry.dry_run is True
        assert dry.total == 3
        assert dry.succeeded == 3
        assert len(dry.per_record) == 3

        rows = client.execute_kw(
            MODEL,
            "read",
            [record_ids],
            {"fields": ["x_status"]},
        )
        assert all(r["x_status"] == "draft" for r in rows)

        live = run_bulk_transition(
            client,
            model=MODEL,
            method=METHOD,
            record_ids=record_ids,
            dry_run=False,
        )
        assert live.dry_run is False
        assert live.succeeded == 3
        assert live.failed == 0
        assert all(r.ok for r in live.per_record)

        rows = client.execute_kw(
            MODEL,
            "read",
            [record_ids],
            {"fields": ["x_status"]},
        )
        assert all(r["x_status"] == "confirmed" for r in rows)
    finally:
        client.execute_kw(MODEL, "unlink", [record_ids])


@pytest.mark.integration
def test_bulk_transition_partial_failure_per_record(
    client: OdooClient, workflow_module: None
) -> None:
    """One record pre-confirmed — batch fails, per-record fallback attributes errors."""
    good_id = int(
        client.execute_kw(
            MODEL,
            "create",
            [{"x_name": "BLK partial ok", "x_status": "draft"}],
        )
    )
    bad_id = int(
        client.execute_kw(
            MODEL,
            "create",
            [{"x_name": "BLK partial bad", "x_status": "confirmed"}],
        )
    )
    try:
        result = run_bulk_transition(
            client,
            model=MODEL,
            method=METHOD,
            record_ids=[good_id, bad_id],
            dry_run=False,
        )
        assert result.succeeded >= 1
        assert result.failed >= 1
        by_id = {r.id: r for r in result.per_record}
        assert by_id[good_id].ok is True
        assert by_id[bad_id].ok is False
        assert by_id[bad_id].error
    finally:
        client.execute_kw(MODEL, "unlink", [[good_id, bad_id]])

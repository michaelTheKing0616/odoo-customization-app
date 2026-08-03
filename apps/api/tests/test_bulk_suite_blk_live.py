"""Live RPC smoke — BLK-2..7 bulk suite on Docker Odoo 19."""

from __future__ import annotations

import os
import uuid
from datetime import date

import pytest

from module_generator import FieldSpec, ModelSpec, ModuleSpec, ViewSpec, build_module_zip
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.attachments import scan_orphan_attachments
from app.bulk_suite.cron_manager import probe_run_method, run_crons_now
from app.bulk_suite.dedupe import merge_duplicates, scan_duplicates
from app.bulk_suite.mass_edit import run_mass_edit
from app.bulk_suite.portal_access import run_bulk_portal
from app.bulk_suite.recompute import probe_recompute
from app.bulk_suite.send_message import run_bulk_send_message
from app.bulk_suite.activities import run_bulk_activities
from app.promote import promote_module_zip

MODULE = "blk_live_smoke"
PARENT = "x_blk_live_parent"
CHILD = "x_blk_live_child"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _live_spec() -> ModuleSpec:
    return ModuleSpec(
        technical_name=MODULE,
        display_name="BLK Live Smoke",
        depends=["base", "mail"],
        models=[
            ModelSpec(
                mode="new",
                model=PARENT,
                description="BLK Live Parent",
                mixins=["mail.thread", "mail.activity.mixin"],
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                    FieldSpec(name="x_tag", ttype="char", string="Tag"),
                ],
            ),
            ModelSpec(
                mode="new",
                model=CHILD,
                description="BLK Live Child",
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name"),
                    FieldSpec(
                        name="x_parent_id",
                        ttype="many2one",
                        string="Parent",
                        relation=PARENT,
                        required=True,
                    ),
                ],
            ),
        ],
        views=[
            ViewSpec(
                name=f"{PARENT}.form",
                model=PARENT,
                type="form",
                arch=(
                    "<form><sheet><group>"
                    '<field name="x_name"/>'
                    '<field name="x_tag"/>'
                    "</group></sheet></form>"
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
        pytest.skip(f"Odoo 19 not reachable for BLK live smoke: {exc}")
    version = c.server_version()
    if not str(version.get("server_version", "")).startswith("19"):
        pytest.skip(f"Expected Odoo 19, got {version.get('server_version')}")
    return c


@pytest.fixture(scope="module")
def blk_module(client: OdooClient) -> None:
    if client.model_exists(PARENT):
        return
    zip_bytes = build_module_zip(_live_spec())
    result = promote_module_zip(client, zip_bytes, restart_container=True)
    assert result.ok, result.message
    assert client.model_exists(PARENT)
    assert client.model_exists(CHILD)


def _create_parent(client: OdooClient, name: str, tag: str = "a") -> int:
    return int(
        client.execute_kw(
            PARENT,
            "create",
            [{"x_name": name, "x_tag": tag}],
        )
    )


@pytest.mark.integration
def test_blk2_mass_edit_live(client: OdooClient, blk_module: None) -> None:
    suffix = uuid.uuid4().hex[:6]
    ids = [_create_parent(client, f"Mass {suffix}-{i}") for i in range(2)]
    try:
        result = run_mass_edit(
            client,
            model=PARENT,
            values={"x_tag": "bulk-edited"},
            record_ids=ids,
            dry_run=False,
        )
        assert result.succeeded == 2
        rows = client.execute_kw(PARENT, "read", [ids], {"fields": ["x_tag"]})
        assert all(r["x_tag"] == "bulk-edited" for r in rows)
    finally:
        client.execute_kw(PARENT, "unlink", [ids])


@pytest.mark.integration
def test_blk3_dedupe_merge_with_child_relink_live(client: OdooClient, blk_module: None) -> None:
    suffix = uuid.uuid4().hex[:6]
    dup_name = f"Dedupe {suffix}"
    winner = _create_parent(client, dup_name, tag="win")
    loser = _create_parent(client, dup_name, tag="lose")
    child_id = int(
        client.execute_kw(
            CHILD,
            "create",
            [{"x_name": "child", "x_parent_id": loser}],
        )
    )
    try:
        scan = scan_duplicates(
            client,
            model=PARENT,
            match_fields=["x_name"],
            mode="exact",
            limit=500,
        )
        assert scan.groups
        dry = merge_duplicates(
            client,
            model=PARENT,
            winner_id=winner,
            loser_ids=[loser],
            dry_run=True,
            force_generic_merge=True,
        )
        assert dry.succeeded == 1
        assert dry.relinks

        live = merge_duplicates(
            client,
            model=PARENT,
            winner_id=winner,
            loser_ids=[loser],
            dry_run=False,
            force_generic_merge=True,
            archive_or_delete="unlink",
        )
        assert live.succeeded == 1
        child = client.execute_kw(
            CHILD,
            "read",
            [[child_id]],
            {"fields": ["x_parent_id"]},
        )[0]
        assert child["x_parent_id"][0] == winner
        assert not client.execute_kw(PARENT, "search", [[("id", "=", loser)]])
    finally:
        client.execute_kw(CHILD, "unlink", [[child_id]])
        client.execute_kw(PARENT, "unlink", [[winner]])


@pytest.mark.integration
def test_blk3_partner_merge_offered_not_error(client: OdooClient) -> None:
    from app.bulk_suite.dedupe import partner_merge_available

    if not partner_merge_available(client):
        pytest.skip("base.partner.merge.automatic.wizard not on instance")
    result = merge_duplicates(
        client,
        model="res.partner",
        winner_id=1,
        loser_ids=[2],
        dry_run=False,
        force_generic_merge=False,
    )
    assert result.partner_merge_recommended is True
    assert result.succeeded == 0
    assert "force_generic_merge" in result.message


@pytest.mark.integration
def test_blk4_cron_run_now_live(client: OdooClient) -> None:
    probe = probe_run_method(client)
    assert probe.get("primary") == "method_direct_trigger"
    cron_ids = client.execute_kw(
        "ir.cron",
        "search",
        [[("active", "=", True)]],
        {"limit": 1},
    )
    if not cron_ids:
        pytest.skip("No active crons on instance")
    dry = run_crons_now(client, cron_ids=cron_ids, dry_run=True)
    assert dry.succeeded >= 1
    live = run_crons_now(client, cron_ids=cron_ids[:1], dry_run=False)
    assert live.run_via in ("method_direct_trigger", "model_method", "dry_run")


@pytest.mark.integration
def test_blk5_attachment_orphan_scan_live(client: OdooClient, blk_module: None) -> None:
    att_id = int(
        client.execute_kw(
            "ir.attachment",
            "create",
            [
                {
                    "name": "blk-orphan-test.txt",
                    "res_model": PARENT,
                    "res_id": 999999999,
                    "datas": "dGVzdA==",
                }
            ],
        )
    )
    try:
        result = scan_orphan_attachments(client, limit=500)
        orphan_ids = {r.id for r in result.orphans}
        assert att_id in orphan_ids
    finally:
        client.execute_kw("ir.attachment", "unlink", [[att_id]])


@pytest.mark.integration
def test_blk6_activities_and_portal_live(client: OdooClient, blk_module: None) -> None:
    client.ensure_module_installed("mail")
    suffix = uuid.uuid4().hex[:6]
    parent_id = _create_parent(client, f"Act {suffix}")
    try:
        type_ids = client.execute_kw(
            "mail.activity.type",
            "search",
            [[]],
            {"limit": 1},
        )
        if not type_ids:
            pytest.skip("No mail.activity.type on instance")
        act = run_bulk_activities(
            client,
            model=PARENT,
            record_ids=[parent_id],
            activity_type_id=int(type_ids[0]),
            summary="BLK smoke follow-up",
            date_deadline=str(date.today()),
            dry_run=True,
        )
        assert act.succeeded == 1

        partner_id = int(
            client.execute_kw(
                "res.partner",
                "create",
                [{"name": f"Portal {suffix}", "email": f"portal-{suffix}@example.com"}],
            )
        )
        portal = run_bulk_portal(
            client,
            partner_ids=[partner_id],
            action="grant",
            dry_run=True,
        )
        assert portal.succeeded == 1
        client.execute_kw("res.partner", "unlink", [[partner_id]])
    finally:
        client.execute_kw(PARENT, "unlink", [[parent_id]])


@pytest.mark.integration
def test_blk7_recompute_probe_and_send_execute_live(client: OdooClient, blk_module: None) -> None:
    client.ensure_module_installed("mail")
    suffix = uuid.uuid4().hex[:6]
    parent_id = _create_parent(client, f"Send {suffix}")
    try:
        probe = probe_recompute(
            client,
            model=PARENT,
            field_name="x_name",
            record_ids=[parent_id],
        )
        assert probe.field == "x_name"

        before = client.execute_kw(
            "mail.message",
            "search_count",
            [[("model", "=", PARENT), ("res_id", "=", parent_id)]],
        )
        result = run_bulk_send_message(
            client,
            model=PARENT,
            record_ids=[parent_id],
            body=f"<p>BLK smoke {suffix}</p>",
            dry_run=False,
        )
        assert result.succeeded == 1
        assert result.failed == 0
        after = client.execute_kw(
            "mail.message",
            "search_count",
            [[("model", "=", PARENT), ("res_id", "=", parent_id)]],
        )
        assert after > before
    finally:
        client.execute_kw(PARENT, "unlink", [[parent_id]])

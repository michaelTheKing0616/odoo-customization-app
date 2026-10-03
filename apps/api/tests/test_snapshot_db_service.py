"""Odoo 20 / Odoo.sh / Online database backups never touch the db service."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from odoo_client.models import ViewInfo

from app.snapshots import snapshot_flow, snapshot_view

pytestmark = pytest.mark.no_app_db


class Odoo20DbEndpointFake:
    """Metadata reads work. Any db-service touch raises."""

    def __init__(self) -> None:
        self.db_endpoint_calls: list[str] = []

    def get_view(self, view_id: int) -> ViewInfo:
        return ViewInfo(
            id=view_id,
            name="Form",
            model="sale.order",
            type="form",
            arch="<form/>",
        )

    def dump_db(self, *_args: object, **_kwargs: object) -> None:
        self._hit("dump_db")

    def __getattr__(self, name: str) -> Any:
        lowered = name.lower()
        if "database" in lowered or lowered in {"dump", "restore", "backup", "exp_dump"}:

            def _call(*_args: object, **_kwargs: object) -> None:
                self._hit(name)

            return _call
        raise AttributeError(name)

    def _hit(self, name: str) -> None:
        self.db_endpoint_calls.append(name)
        raise AssertionError(f"/web/database via {name}")


def test_db_endpoint_fake_raises_when_dump_is_called() -> None:
    client = Odoo20DbEndpointFake()
    with pytest.raises(AssertionError, match="/web/database"):
        client.dump_db("odoo")
    with pytest.raises(AssertionError, match="/web/database"):
        client.web_database("/web/database/backup")


def test_snapshot_refuses_on_odoo_sh_and_online() -> None:
    client = Odoo20DbEndpointFake()
    db = MagicMock()
    for hosting in ("self_hosted", "odoo_sh", "online"):
        snap = snapshot_flow(
            kind="metadata",
            client=client,
            odoo_major=20,
            hosting_hint=hosting,
            metadata_snapshot=lambda c: snapshot_view(db, "conn-20", c, 7),
        )
        assert snap.resource_type == "view"
        assert snap.resource_key == "view:7"
    assert client.db_endpoint_calls == []

    for hosting in ("odoo_sh", "Odoo.sh", "online", "Odoo Online"):
        for major in (19, 20):
            result = snapshot_flow(
                kind="database",
                client=client,
                odoo_major=major,
                hosting_hint=hosting,
            )
            assert result["refused"] is True
            assert result["called_db_service"] is False
            assert "Take the database backup on the host" in result["message"]
            assert "/web/database" in result["message"]
            assert "dump_db" in result["message"]
    assert client.db_endpoint_calls == []


def test_major_20_database_backup_asks_the_operator() -> None:
    client = Odoo20DbEndpointFake()
    result = snapshot_flow(
        kind="database",
        client=client,
        odoo_major=20,
        hosting_hint="self_hosted",
    )
    assert result["ok"] is False
    assert result["refused"] is True
    assert result["called_db_service"] is False
    assert "Odoo 20 has no database service" in result["message"]
    assert "Odoo Online, Odoo.sh, or the server" in result["message"]
    assert client.db_endpoint_calls == []

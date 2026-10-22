import time
from types import SimpleNamespace

from app import ai_schema_client as sc, odoo_snapshot as osn
from app.schema_freshness import SCHEMA_TTL_S, is_fresh


def test_one_rule_shared():
    assert osn._TTL == sc.SCHEMA_CATALOG_TTL_S == SCHEMA_TTL_S
    assert is_fresh(time.time()) and not is_fresh(time.time() - SCHEMA_TTL_S - 1) and not is_fresh(None)


def _draft(age):
    return {"_connection_catalog": {"stock": [{"model": "res.partner"}], "loaded_at": time.time() - age}}


def test_stale_catalog_uses_fresh_request_snapshot_else_denies():
    assert isinstance(sc.schema_client_for_draft(_draft(SCHEMA_TTL_S + 5)), sc.DenySchemaClient)
    snap = SimpleNamespace(ok=True, captured_at=time.time(), index={"x_a": "A"}, models={})
    tok = osn.set_snapshot(snap)
    try:
        c = sc.schema_client_for_draft(_draft(SCHEMA_TTL_S + 5))
        assert c.model_exists("x_a")
        snap.captured_at = time.time() - SCHEMA_TTL_S - 5
        assert isinstance(sc.schema_client_for_draft(_draft(SCHEMA_TTL_S + 5)), sc.DenySchemaClient)
    finally:
        osn._SNAPSHOT.reset(tok)

"""Hosting choice: saved > saas~ version > URL (Tope, Oct 20)."""
import pytest

from app.hosting import connection_hosting, hosting_hint_from_url
from app.tier_matrix import build_tier_context

pytestmark = pytest.mark.no_app_db


def test_detection_order():
    assert hosting_hint_from_url("https://acme.odoo.com") == "online"
    assert hosting_hint_from_url("https://odoo.acme.ng", "saas~18.2+e") == "online"
    assert hosting_hint_from_url("https://acme-main-123.dev.odoo.com") == "odoo_sh"
    assert hosting_hint_from_url("https://acme.odoo.sh") == "odoo_sh"
    assert hosting_hint_from_url("https://erp.acme.ng", "18.0") == "self_hosted"
    assert hosting_hint_from_url("https://acme.odoo.com", None, "self_hosted") == "self_hosted"
    assert hosting_hint_from_url("https://x.ng", None, "bogus") == "self_hosted"


def test_connection_and_tier_respect_saved():
    class C:
        url = "https://erp.acme.ng"
        server_version = "18.0"
        hosting = "online"

    assert connection_hosting(C()) == "online"
    ctx = build_tier_context(url=C.url, server_version="18.0", saved_hosting="online")
    assert ctx.hosting == "online"
    ctx2 = build_tier_context(url=C.url, server_version="18.0")
    assert ctx2.hosting == "onprem"

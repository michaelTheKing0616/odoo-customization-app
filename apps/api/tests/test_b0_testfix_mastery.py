"""Pin P0-2-CL4.

Community Online operator copy is one exact sentence. Enterprise starts with
that sentence and then names the Enterprise edition and Studio.
"""

from __future__ import annotations

import pytest

from app.hosting import hosting_operator_message

pytestmark = pytest.mark.no_app_db

# Ledger sentence. Deleting it from hosting_operator_message fails the tests below.
ONLINE_REFUSE_EXACT = (
    "Hosting looks like Odoo Online: metadata customization and data/XML "
    "module import are OK; custom Python modules cannot be installed on Online — "
    "export install_mode=data or use Odoo.sh / self-host for custom-code Python."
)


def test_online_community_operator_message_equals_refuse_exact() -> None:
    """Fails if the Online community sentence in hosting_operator_message is deleted.

    Product line: apps/api/app/hosting.py, the ``hosting_hint == "online"`` string.
    """
    assert hosting_operator_message("online", edition="community") == ONLINE_REFUSE_EXACT


def test_online_enterprise_operator_message_appends_studio_warn() -> None:
    """Fails if the Online sentence or the Enterprise Studio warning is deleted.

    Product lines: the same Online string, then the ``edition == "enterprise"``
    string in hosting_operator_message (Enterprise edition detected / Studio).
    """
    msg = hosting_operator_message("online", edition="enterprise")
    assert msg.startswith(ONLINE_REFUSE_EXACT)
    assert msg != ONLINE_REFUSE_EXACT
    assert "Enterprise edition detected" in msg
    assert "Studio" in msg

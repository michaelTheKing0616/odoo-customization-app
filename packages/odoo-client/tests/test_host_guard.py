import socket

import pytest


@pytest.mark.parametrize("host", ["aonb.odoo.com", "acme.odoo.com", "client.odoo.sh"])
def test_guard_refuses_client_hosts(host):
    with pytest.raises(ConnectionRefusedError):
        socket.getaddrinfo(host, 443)
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection((host, 443), timeout=1)


def test_guard_allows_localhost():
    assert socket.getaddrinfo("127.0.0.1", 80)

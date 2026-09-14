"""App metadata DB bootstrap helpers (no live Postgres required)."""

from app.db import _db_unreachable_message, _is_postgres_url


def test_postgres_url_detection() -> None:
    assert _is_postgres_url(
        "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom"
    )
    assert not _is_postgres_url("sqlite+pysqlite:///:memory:")


def test_unreachable_message_points_at_app_db() -> None:
    msg = _db_unreachable_message()
    assert "app-db" in msg
    assert "docker compose" in msg
    assert "odoo_custom:odoo_custom" not in msg

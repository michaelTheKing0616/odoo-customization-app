"""POST /api/connections/{id}/module-spec/option-a-repair-feedback end to end.

Route -> repair_option_a_from_feedback -> (optional) sandbox prove, with a fake
LLM (``_default_repair_blocks`` patched) and a fake sandbox
(``prove_option_a_in_sandbox`` patched). No Docker, no live model.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from tests.test_ai_option_a_feedback import (  # noqa: E402
    PYTHON_INHERIT,
    RUNTIME_FAULT,
    _authored_draft,
)

_PATCHED = PYTHON_INHERIT.replace("standard_price or 0", "standard_price or 0.0")


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _connection(url: str = "http://127.0.0.1:8069") -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="repair-feedback-route",
            url=url,
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _url(cid: str) -> str:
    return f"/api/connections/{cid}/module-spec/option-a-repair-feedback"


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    import app.ai_option_a_feedback as fb

    prompts: list[str] = []

    def fake(prompt: str, draft: dict[str, Any]) -> list[dict[str, Any]]:
        prompts.append(prompt)
        return [{"source_file": "models/sale_markup.py", "content": _PATCHED}]

    monkeypatch.setattr(fb, "_default_repair_blocks", fake)
    return prompts


def _fake_sandbox(monkeypatch: pytest.MonkeyPatch, *, ok: bool) -> list[dict[str, Any]]:
    import app.ai_option_a_quality as q

    seen: list[dict[str, Any]] = []

    def fake_prove(spec: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        seen.append({"spec": spec, **kwargs})
        msg = "Sandbox install & smoke passed" if ok else RUNTIME_FAULT
        spec["_sandbox_install"] = {"ok": ok, "message": msg}
        return {"ok": ok, "draft": spec, "message": msg, "smoke": {"ok": ok, "message": msg}}

    monkeypatch.setattr(q, "prove_option_a_in_sandbox", fake_prove)
    return seen


def test_repair_then_sandbox_proves(
    client: TestClient, fake_llm: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = _fake_sandbox(monkeypatch, ok=True)
    res = client.post(
        _url(_connection()),
        json={"spec": _authored_draft(), "error_text": RUNTIME_FAULT, "retry_sandbox": True},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["feedback_repair"]["applied"] is True
    assert body["feedback_repair"]["llm"] is True
    assert body["feedback_repair"]["files"] == ["models/sale_markup.py"]
    assert len(fake_llm) == 1 and "standard_cost" in fake_llm[0]
    assert len(sandbox) == 1
    assert sandbox[0]["auto_repair"] is False and sandbox[0]["run_tests"] is True
    patched = {b["source_file"]: b["content"] for b in sandbox[0]["spec"]["custom_code_blocks"]}
    assert "standard_price or 0.0" in patched["models/sale_markup.py"]


def test_repair_applied_but_sandbox_still_fails(
    client: TestClient, fake_llm: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_sandbox(monkeypatch, ok=False)
    res = client.post(
        _url(_connection()),
        json={"spec": _authored_draft(), "error_text": RUNTIME_FAULT, "retry_sandbox": True},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["feedback_repair"]["applied"] is True
    assert "standard_cost" in body["message"]


def test_repair_without_retry_returns_patched_draft(
    client: TestClient, fake_llm: list[str]
) -> None:
    res = client.post(
        _url(_connection()), json={"spec": _authored_draft(), "error_text": RUNTIME_FAULT}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert "Retry Sandbox install" in body["message"]
    blocks = {b["source_file"]: b["content"] for b in body["draft"]["custom_code_blocks"]}
    assert "standard_price or 0.0" in blocks["models/sale_markup.py"]


def test_budget_exhausted_is_honest(
    client: TestClient, fake_llm: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = _fake_sandbox(monkeypatch, ok=True)
    spec = _authored_draft()
    spec["_sandbox_repair_count"] = 3
    res = client.post(
        _url(_connection()), json={"spec": spec, "error_text": RUNTIME_FAULT, "retry_sandbox": True}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["feedback_repair"]["reason"] == "max_repair_exceeded"
    assert "budget" in body["message"].lower()
    assert "Download module zip" in body["message"]
    assert fake_llm == [] and sandbox == []  # no model call, no sandbox retry


def test_odoo_online_is_refused_honestly(client: TestClient, fake_llm: list[str]) -> None:
    res = client.post(
        _url(_connection("https://acme.odoo.com")),
        json={"spec": _authored_draft(), "error_text": RUNTIME_FAULT, "retry_sandbox": True},
    )
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert "not available on Odoo Online" in detail
    assert "Odoo.sh or a self-hosted server" in detail
    assert "\u2014" not in detail
    assert fake_llm == []


@pytest.mark.parametrize(
    "payload",
    [{}, {"spec": []}, {"spec": "not a dict"}, {"spec": {}, "retry_sandbox": "maybe"}],
)
def test_bad_input_is_4xx(client: TestClient, payload: dict[str, Any]) -> None:
    res = client.post(_url(_connection()), json=payload)
    assert res.status_code == 422

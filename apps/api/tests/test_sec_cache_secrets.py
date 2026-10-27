"""SEC-CACHE-SECRETS AC1: the shared AI answer cache stores no secrets or personal data,
and a fresh answer skips cache reads.

Product lines whose deletion fails these tests:
- apps/api/app/ai_client/shared_client.py:95 (fresh flag)
- apps/api/app/ai_client/shared_client.py:135-139 (redact before the cache write)
- apps/api/app/ai_client/shared_client.py:156-159 (skip the read on fresh)
- apps/api/app/ai_client/shared_client.py:182-185 (skip the write when sensitive)
- apps/api/app/ai_client/shared_client.py:212-216 (_looks_sensitive)
- apps/api/app/ai_client/ai_scope.py:76-77 (x-ingenium-fresh)
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.ai_client import ai_cache
from app.ai_client.ai_scope import AIScopeMiddleware, ai_scope, current_scope
from app.ai_client.shared_client import wrap
from app.llm_provider import LLMProvider

pytestmark = pytest.mark.no_app_db

_PHONE = "+234 803 123 4567"
_EMAIL = "ada@client.ng"
_PASSWORD = "SuperSecret99"
_API_KEY = "sk-proj-abcdefghijklmnopqrstuvwxyz"
_PLAIN = "What is a journal entry?"
_PLAIN_REPLY = "ledger-posting-note-8841"


class _Fake(LLMProvider):
    def __init__(self, reply: str | object = _PLAIN_REPLY, name: str = "gemini") -> None:
        self.calls: list[tuple[str, dict]] = []
        self.reply = reply
        self._name = name
        self.model = "gemini-flash"

    @property
    def name(self) -> str:
        return self._name

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        return True, "ok"

    def generate_json(self, prompt: str, **kw: object) -> str:
        self.calls.append((prompt, dict(kw)))
        if callable(self.reply):
            return self.reply(prompt, kw)
        return str(self.reply)


@pytest.fixture(autouse=True)
def _guards_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGENIUM_GUARD_HISTORY", "off")
    monkeypatch.setenv("INGENIUM_GUARD_MODEL", "off")


def _cache_blob(tmp_path: Path) -> bytes:
    """Bytes of this test's answer-cache file, including the WAL."""
    db = tmp_path / "ai_cache.sqlite"
    try:
        ai_cache._db().execute("PRAGMA wal_checkpoint(FULL)")
    except Exception:  # noqa: BLE001 — a missing file still has nothing to leak
        pass
    parts: list[bytes] = []
    for path in (db, Path(str(db) + "-wal"), Path(str(db) + "-shm")):
        if path.exists():
            parts.append(path.read_bytes())
    return b"".join(parts)


def test_plain_answer_is_cached_so_a_skip_is_observable(tmp_path: Path) -> None:
    """Deleting shared_client.py:186 (the put) makes the second call miss."""
    provider = _Fake(reply=_PLAIN_REPLY, name="ollama")
    client = wrap(provider)
    assert client.generate_text(_PLAIN) == _PLAIN_REPLY
    assert client.generate_text(_PLAIN) == _PLAIN_REPLY
    assert len(provider.calls) == 1
    assert _PLAIN_REPLY.encode() in _cache_blob(tmp_path)


def test_local_cache_skips_phone_email_and_password(tmp_path: Path) -> None:
    """Deleting shared_client.py:182-185 stores the secret and the repeat call hits."""
    provider = _Fake(reply="ok", name="ollama")
    client = wrap(provider)
    prompts = (
        f"Call Ada on {_PHONE}",
        f"Email {_EMAIL} about the invoice",
        f"password={_PASSWORD}",
    )
    for prompt in prompts:
        client.generate_text(prompt)
        client.generate_text(prompt)
    assert len(provider.calls) == 6
    assert ai_cache.stats()["not_cached_sensitive"] == 6
    blob = _cache_blob(tmp_path)
    for needle in (
        _PHONE.encode(),
        b"803 123 4567",
        _EMAIL.encode(),
        b"ada client ng",
        _PASSWORD.encode(),
        _PASSWORD.lower().encode(),
    ):
        assert needle not in blob


def test_local_model_output_email_is_not_cached(tmp_path: Path) -> None:
    """Deleting the red-is-None clause in shared_client.py:182 caches the email."""
    provider = _Fake(reply=f"Reach {_EMAIL} tomorrow", name="ollama")
    client = wrap(provider)
    prompt = "Write one contact line for the buyer"
    client.generate_text(prompt)
    client.generate_text(prompt)
    assert len(provider.calls) == 2
    assert ai_cache.stats()["not_cached_sensitive"] == 2
    assert _EMAIL.encode() not in _cache_blob(tmp_path)


def test_cloud_cache_stores_placeholders_not_cleartext(tmp_path: Path) -> None:
    """Deleting shared_client.py:135-139 leaves the email and key in the cache file."""
    provider = _Fake(
        reply=lambda prompt, _kw: "noted " + prompt,
        name="gemini",
    )
    client = wrap(provider)
    prompt = f"Use {_EMAIL} and key {_API_KEY} and password={_PASSWORD}"
    first = client.generate_text(prompt)
    second = client.generate_text(prompt)
    assert first == second
    assert _EMAIL in first and _API_KEY in first and _PASSWORD in first
    sent = provider.calls[0][0]
    assert _EMAIL not in sent and _API_KEY not in sent and _PASSWORD not in sent
    assert len(provider.calls) == 1
    blob = _cache_blob(tmp_path)
    needles = (
        _EMAIL.encode(),
        _API_KEY.encode(),
        _PASSWORD.encode(),
        _PASSWORD.lower().encode(),
    )
    for needle in needles:
        assert needle not in blob


def test_cloud_output_api_key_is_not_cached(tmp_path: Path) -> None:
    """Deleting shared_client.py:182-185 reuses the first answer and skips the sensitive bump."""
    provider = _Fake(reply=f"key {_API_KEY}", name="gemini")
    client = wrap(provider)
    prompt = "Summarise this internal note"
    first = client.generate_text(prompt)
    client.generate_text(prompt)
    assert _API_KEY not in first
    assert len(provider.calls) == 2
    assert ai_cache.stats()["not_cached_sensitive"] == 2
    assert _API_KEY.encode() not in _cache_blob(tmp_path)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CACHE-H-EMAIL: cloud answers that contain an email are stored. "
        "shared_client.py:182 calls _looks_sensitive only when red is None, and "
        "check_output does not flag emails on the internal surface (guards.py:426), "
        "so ai_cache.put keeps the address."
    ),
)
def test_cloud_model_output_email_is_not_cached(tmp_path: Path) -> None:
    """AC1 forbids a personal email in the answer cache, including model output."""
    provider = _Fake(reply=f"Reach {_EMAIL} tomorrow", name="gemini")
    client = wrap(provider)
    prompt = "Write one contact line for the buyer"
    client.generate_text(prompt)
    client.generate_text(prompt)
    assert _EMAIL.encode() not in _cache_blob(tmp_path)
    assert len(provider.calls) == 2
    assert ai_cache.stats()["not_cached_sensitive"] == 2


def test_fresh_kw_and_scope_skip_cache_reads() -> None:
    """Deleting shared_client.py:95 or :156-159 serves the cached answer on a fresh call."""
    provider = _Fake(reply=_PLAIN_REPLY, name="gemini")
    client = wrap(provider)
    client.generate_text(_PLAIN)
    client.generate_text(_PLAIN, fresh=True)
    with ai_scope(fresh=True):
        client.generate_text(_PLAIN)
    assert len(provider.calls) == 3
    assert ai_cache.stats()["bypass_fresh"] == 2
    assert "fresh" not in provider.calls[1][1]
    client.generate_text(_PLAIN)
    assert len(provider.calls) == 3
    assert ai_cache.stats()["hits_exact"] == 1


def test_fresh_header_is_the_bypass_switch() -> None:
    """Deleting ai_scope.py:76-77 leaves fresh false when the header is 1 or true."""

    async def _seen(headers: list[tuple[bytes, bytes]]) -> bool:
        box: dict[str, bool] = {}

        async def app(scope: dict, receive: object, send: object) -> None:
            box["fresh"] = current_scope().fresh

        await AIScopeMiddleware(app)(
            {"type": "http", "path": "/api/connections/c1/ask", "headers": headers},
            None,
            None,
        )
        return box["fresh"]

    assert asyncio.run(_seen([(b"x-ingenium-fresh", b"1")])) is True
    assert asyncio.run(_seen([(b"x-ingenium-fresh", b"true")])) is True
    assert asyncio.run(_seen([(b"x-ingenium-fresh", b"0")])) is False
    assert asyncio.run(_seen([])) is False

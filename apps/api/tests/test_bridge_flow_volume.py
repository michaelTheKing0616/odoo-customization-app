"""Bridge monitor exposes a 12-step volume series for the sparkline (touch 55/59)."""
from app.bridge import flows


def test_monitor_volume_buckets(monkeypatch) -> None:  # noqa: ANN001
    now = 10_000.0
    data = {"f1|r1": [{"at": now - 3500, "status": "done"}, {"at": now - 10, "status": "failed"}],
            "f2|r9": [{"at": now - 10, "status": "done"}]}
    monkeypatch.setattr(flows.store, "load", lambda *_a, **_k: data)
    m = flows.monitor(None, "f1", now=now)
    assert len(m["volume"]) == 12 and sum(m["volume"]) == 2
    assert m["volume"][0] == 1 and m["volume"][-1] == 1

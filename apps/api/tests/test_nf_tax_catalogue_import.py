"""TAX-CATALOGUE-IMPORT: schema, adversarial and drift tests for app.catalogue."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from app.catalogue import loader as L

RAW = L.CSV_FILE.read_bytes()
LINES = RAW.split(b"\r\n")
HEADER = LINES[0]
ROWS_JSON = Path(L.__file__).parents[1] / "bots" / "risk" / "catalogue_rows.json"


def _sample(n: int = 400) -> list[bytes]:
    return [HEADER, *LINES[1 : n + 1]]


def _bytes(lines: list[bytes]) -> bytes:
    return b"\r\n".join(lines) + b"\r\n"


def _first(cls: str) -> int:
    return next(i for i, ln in enumerate(LINES) if f",{cls},".encode() in ln and i > 400)


def _cells(line: bytes) -> list[str]:
    import csv

    return next(csv.reader([line.decode()]))


def _join(cells: list[str]) -> bytes:
    import csv
    import io

    b = io.StringIO()
    csv.writer(b, lineterminator="").writerow(cells)
    return b.getvalue().encode()


def _mutate(col: str, value: str, cls: str = "R1") -> bytes:
    i = _first(cls)
    c = _cells(LINES[i])
    c[L.COLUMNS.index(col)] = value
    return _bytes([*_sample(), _join(c)])


# ------------------------------------------------------------------ schema / happy path
def test_loads_full_catalogue() -> None:
    cat = L.load()
    assert len(cat.tasks) == 11937 == len(cat.index)
    assert Counter(t.tier for t in cat.tasks) == {"T1": 6848, "T2": 4729, "T3": 360}
    assert {t.risk_class for t in cat.tasks} == set(L.CLASS_PROFILE)
    assert all(t.versions <= L.VERSIONS and "audit" in t.controls for t in cat.tasks)
    t = L.by_id("b:account.account:action_open_related_taxes")
    assert t and t.risk_class == "R2W" and t.versions == frozenset({17, 18, 19, 20})
    assert L.by_id("b:nope:nope") is None
    assert L.by_id("cron:Lunch: send automatic email to {supplier}")  # runtime-templated name
    assert len([t for t in cat.tasks if t.object == "ir.mail_server"]) == 7
    assert 0 < len(L.tasks_for_version(17)) < len(cat.tasks)
    with pytest.raises(L.CatalogueError):
        L.tasks_for_version(16)


def test_task_is_immutable() -> None:
    t = L.load().tasks[0]
    with pytest.raises(AttributeError):
        t.risk_class = "R0"  # type: ignore[misc]


# ------------------------------------------------------------------ drift
def test_meta_pins_data() -> None:
    meta = json.loads(L.META_FILE.read_text())
    assert meta["sha256"] == hashlib.sha256(RAW).hexdigest()
    assert meta["rows"] == 11937 and tuple(meta["columns"]) == L.COLUMNS


def test_same_source_as_risk_classifier() -> None:
    doc = json.loads(ROWS_JSON.read_text())
    assert doc["sha256"] == hashlib.sha256(RAW).hexdigest(), (
        "catalogue.csv and catalogue_rows.json drifted"
    )
    groups = {i: k for k, ids in doc["groups"].items() for i in ids}
    cat = L.load()
    assert len(groups) == doc["rows_total"] == len(cat.tasks)
    for t in cat.tasks:
        assert groups[t.id] == t.risk_class + "|" + "|".join(str(v) for v in sorted(t.versions)), (
            t.id
        )
    assert set(doc["irreversible"]) <= set(cat.index)
    # the classifier's control map may only be stricter: every class it knows exists here
    assert set(doc["controls"]) == set(L.CLASS_PROFILE)


def test_git_keeps_bytes_verbatim() -> None:
    attrs = (L.DATA_DIR / ".gitattributes").read_text()
    assert "catalogue.csv -text" in attrs  # no CRLF normalization, else the sha pin breaks


def test_class_profile_matches_risk_model_doc() -> None:
    names = {t.risk_class: t.risk_name for t in L.load().tasks}
    assert names == {k: v[0] for k, v in L.CLASS_PROFILE.items()}


# ------------------------------------------------------------------ adversarial
def test_sample_parses() -> None:
    assert len(L.parse(_bytes(_sample())).tasks) == 400


@pytest.mark.parametrize(
    ("raw", "why"),
    [
        pytest.param(b"", "empty or malformed", id="empty"),
        pytest.param(_bytes([HEADER]), "no rows", id="header-only"),
        pytest.param(b"\xef\xbb\xbf" + _bytes(_sample()), "BOM", id="bom"),
        pytest.param(
            _bytes([HEADER.replace(b"id,area", b"area,id"), *LINES[1:5]]),
            "header",
            id="header-reorder",
        ),
        pytest.param(_bytes([HEADER + b",x", *LINES[1:5]]), "header", id="extra-column"),
        pytest.param(_bytes([*_sample(), LINES[1]]), "duplicate", id="duplicate-id"),
        pytest.param(_bytes([*_sample(), LINES[2] + b",extra"]), "cells", id="extra-cell"),
        pytest.param(
            _bytes([*_sample(), b'"unterminated,' + LINES[3]]),
            "malformed|cells",
            id="unclosed-quote",
        ),
        pytest.param(_mutate("tier", "T4"), "tier", id="tier"),
        pytest.param(_mutate("versions", "17|21"), "versions", id="version-21"),
        pytest.param(_mutate("versions", "19|17"), "versions", id="versions-unsorted"),
        pytest.param(_mutate("versions", "17|17"), "versions", id="versions-dup"),
        pytest.param(_mutate("versions", ""), "versions", id="versions-empty"),
        pytest.param(_mutate("risk_class", "R10"), "unknown risk class", id="unknown-class"),
        pytest.param(
            _mutate("risk_class", "R1", cls="R6"), "profile drift", id="relabel-delete-as-draft"
        ),
        pytest.param(_mutate("blast", "low", cls="R9"), "profile drift", id="blast-downgrade"),
        pytest.param(
            _mutate("controls", "readback;idempotency-key"), "include audit", id="no-audit"
        ),
        pytest.param(_mutate("controls", "audit;audit;readback"), "distinct", id="dup-control"),
        pytest.param(_mutate("controls", "audit;;readback"), "non-empty", id="empty-control"),
        pytest.param(
            _mutate("controls", "audit;readback;idempotency-key;x"),
            "controls differ",
            id="sibling-drift",
        ),
        pytest.param(
            _mutate("controls", "clone-rehearsal;audit", cls="R3"),
            "human approval",
            id="R3-no-approval",
        ),
        pytest.param(_mutate("object", '=HYPERLINK("http://x")'), "formula", id="formula"),
        pytest.param(_mutate("note", "@SUM(A1)"), "formula", id="formula-note"),
        pytest.param(_mutate("object", "a\nb"), "unsafe", id="newline"),
        pytest.param(_mutate("object", "a\x00b"), "unsafe", id="nul"),
        pytest.param(_mutate("object", "caf\u00e9"), "ASCII", id="non-ascii"),
        pytest.param(_mutate("object", " padded"), "whitespace", id="whitespace"),
        pytest.param(_mutate("object", ""), "empty", id="empty-object"),
        pytest.param(_mutate("object", "x" * 600), "oversized", id="oversized"),
        pytest.param(_mutate("id", "zz:res.partner"), "bad id", id="unknown-id-kind"),
        pytest.param(_mutate("id", "m:res.partner;drop"), "bad id", id="id-charset"),
    ],
)
def test_refuses_defects(raw: bytes, why: str) -> None:
    with pytest.raises(L.CatalogueError, match=why):
        L.parse(raw)


def test_refuses_tampered_bytes_against_pin() -> None:
    tampered = RAW.replace(b",R6,", b",R1,", 1)
    with pytest.raises(L.CatalogueError, match="sha256"):
        L.parse(tampered, hashlib.sha256(RAW).hexdigest())


def _patch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, csv_bytes: bytes | None, meta: object
) -> None:
    c, m = tmp_path / "catalogue.csv", tmp_path / "catalogue.meta.json"
    if csv_bytes is not None:
        c.write_bytes(csv_bytes)
    if meta is not None:
        m.write_text(meta if isinstance(meta, str) else json.dumps(meta))
    monkeypatch.setattr(L, "CSV_FILE", c)
    monkeypatch.setattr(L, "META_FILE", m)
    L.load.cache_clear()


@pytest.mark.parametrize(
    ("csv_bytes", "meta"),
    [
        pytest.param(RAW, None, id="meta-missing"),
        pytest.param(RAW, "{not json", id="meta-garbled"),
        pytest.param(RAW, {"sha256": "abc"}, id="meta-bad-sha"),
        pytest.param(None, {"sha256": "0" * 64, "rows": 1}, id="csv-missing"),
        pytest.param(
            RAW, {"sha256": hashlib.sha256(RAW).hexdigest(), "rows": 11928}, id="row-count"
        ),
        pytest.param(
            RAW + b"x", {"sha256": hashlib.sha256(RAW).hexdigest(), "rows": 11937}, id="appended"
        ),
    ],
)
def test_load_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, csv_bytes: bytes | None, meta: object
) -> None:
    _patch(monkeypatch, tmp_path, csv_bytes, meta)
    try:
        with pytest.raises(L.CatalogueError):
            L.load()
    finally:
        monkeypatch.undo()
        L.load.cache_clear()


def test_import_rejects_bad_source_without_touching_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    good = _bytes(_sample(50))
    meta = {"sha256": hashlib.sha256(good).hexdigest(), "rows": 50}
    _patch(monkeypatch, tmp_path, good, meta)
    before = (L.CSV_FILE.read_bytes(), L.META_FILE.read_bytes())
    bad = tmp_path / "bad.csv"
    bad.write_bytes(_mutate("tier", "T9"))
    try:
        with pytest.raises(L.CatalogueError):
            L.import_csv(bad)
        assert (L.CSV_FILE.read_bytes(), L.META_FILE.read_bytes()) == before
        src = tmp_path / "new.csv"
        src.write_bytes(_bytes(_sample(60)))
        assert len(L.import_csv(src).tasks) == 60 and len(L.load().tasks) == 60
        assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]
    finally:
        monkeypatch.undo()
        L.load.cache_clear()
    assert len(L.load().tasks) == 11937

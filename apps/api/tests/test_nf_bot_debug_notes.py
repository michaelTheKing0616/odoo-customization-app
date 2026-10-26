# ruff: noqa: E501 - rendered Odoo messages stay on one line
"""BOT-ODOO-DEBUG-NOTES acceptance tests (offline; evidence file comes from the odoo images)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

from app.bots import debug_notes as dn
from app.bots import tiers as tt

EVIDENCE = Path(__file__).resolve().parents[1] / "evals" / "bots" / "debug_notes_evidence.json"

# Rendered samples (message templates from the cited sources, filled with example values).
SAMPLES = {
    "xmlid-not-found": "ValueError: External ID not found in the system: x_mod.action_missing",
    "singleton": "ValueError: Expected singleton: res.partner(3, 7)",
    "xpath-not-located": "Element '<xpath expr=\"//field[@name='x']\">' cannot be located in parent view",
    "invalid-field": "ValueError: Invalid field 'x_old' on model 'res.partner'",
    "view-field-missing": 'Field "x_gone" does not exist in model "sale.order"',
    "missing-record": "odoo.exceptions.MissingError: Record does not exist or has been deleted.",
    "module-load-failed": "CRITICAL db odoo.modules.module: Couldn't load module x_mod",
    "modules-not-loaded": "ERROR db odoo.modules.loading: Some modules are not loaded, some dependencies or manifest may be missing: ['x_mod']",
    "modules-inconsistent": "ERROR db odoo.modules.loading: Some modules have inconsistent states, some dependencies may be missing: ['x_mod']",
    "registry-load-failed": "ERROR db odoo.modules.registry: Failed to load registry",
    "smtp-failed": "Mail delivery failed via SMTP server 'smtp.example.com'.\nSMTPAuthenticationError: bad",
    "wrong-value": "ValueError: Wrong value for x.model.x_state: 'nope'",
    "recursion": "odoo.exceptions.UserError: Recursion Detected.",
    "import-no-match": "No matching record found for name 'ACME' in field 'Customer'",
    "unknown-currency-field": "AssertionError: Field x.model.x_cost with unknown currency_field 'x_currency_id'",
    "unknown-comodel": "WARNING db odoo.fields: Field x.model.x_tag_ids with unknown comodel_name 'x.tag'",
    "access-denied": "You are not allowed to access 'Request' (x.request) records.",
    "cron-running": "Record cannot be modified right now: This cron task is currently being executed",
    "missing-required": "Missing required value for the field 'Name' (x_name)",
    "composed-field": "Invalid composed field partner_id.x_gone in domain",
    "field-in-views": "Cannot rename/delete fields that are still present in views:\nFields: x.model.x_a",
    "template-render-failed": "Failed to render template: mail.template(4,)",
    "qweb-render-error": "odoo.addons.base.models.ir_qweb.QWebException: Error while rendering the template",
    "invalid-view-definition": "Invalid view x_mod.view_form definition in x_mod/views/views.xml",
    "view-validation": "Error while validating view near:",
    "fk-delete-blocked": "The operation cannot be completed: another model requires the record being deleted.",
    "mandatory-not-set": "- Create/update: a mandatory field is not set.",
    "invalid-leaf": "ValueError: Invalid leaf ('a', 'b')",
    "invalid-operator": "ValueError: Invalid operator 'like!' in domain term",
    "cron-action-failed": "ERROR db odoo.addons.base.models.ir_cron: Job 'Digest' (5) server action #12 failed",
}


# AC1 catalogue: >=25 signatures, each verified against odoo:17-20 sources with file cited
def test_catalogue_size_and_shape():
    assert len(dn.CATALOGUE) >= 25
    for s in dn.CATALOGUE:
        assert s.needles and set(s.needles) == set(s.files) <= set(dn.VERSIONS)
        assert s.cause and s.diagnosis and s.dont and s.fix_kind
        assert s.fix_tier in (tt.T1, tt.T2, tt.T3)


def test_every_needle_verified_in_image_source():
    ev = json.loads(EVIDENCE.read_text())
    assert set(ev) == {s.id for s in dn.CATALOGUE}
    for s in dn.CATALOGUE:
        for v in s.versions:
            r = ev[s.id][str(v)]
            assert r["ok"] and r["line"] > 0 and r["file"] == s.files[v], (s.id, v)


# AC2 matcher: ranked matches with evidence; every signature is reachable
@pytest.mark.parametrize("sid", sorted(SAMPLES))
def test_each_signature_matches_its_sample(sid):
    v = next(s for s in dn.CATALOGUE if s.id == sid).versions[-1]
    r = dn.match("Traceback (most recent call last):\n  ...\n" + SAMPLES[sid], version=v)
    assert r.status == "matched" and sid in [m.id for m in r.matches]
    m = next(m for m in r.matches if m.id == sid)
    assert m.evidence and m.evidence[0]["line"] >= 3 and m.source_files[v]


def test_samples_cover_catalogue():
    assert set(SAMPLES) == {s.id for s in dn.CATALOGUE}


def test_ranking_prefers_final_error():
    log = (
        SAMPLES["registry-load-failed"] + "\n" + "\n".join(["x"] * 50) + "\n" + SAMPLES["singleton"]
    )
    r = dn.match(log, version=17)
    assert r.matches[0].id == "singleton"


def test_version_filter():
    assert dn.match(SAMPLES["recursion"], version=20).status == "unknown"
    assert dn.match(SAMPLES["recursion"], version=17).status == "matched"


# AC3 unknown never guesses
@pytest.mark.parametrize("text", ["", "all good", "KeyError: 'foo'", "Expected single", "x" * 1000])
def test_unknown_has_no_fix(text):
    r = dn.match(text)
    assert r.status == "unknown" and r.matches == []
    assert "fix" not in json.dumps(r.to_dict())


# AC4 hostile input: bounded, ReDoS-safe, never raises
@pytest.mark.parametrize(
    "text,status",
    [
        (None, "invalid"),
        (123, "invalid"),
        (b"\xff\xfe" * 10, "unknown"),
        ("a" * (dn.MAX_INPUT + 1), "invalid"),
    ],
)
def test_bad_input_fails_closed(text, status):
    assert dn.match(text).status == status


def test_bad_version():
    for v in (16, "17", 17.0, True):
        assert dn.match("x", version=v).status == "invalid"


def test_redos_timing():
    evil = [
        "Element " + "a" * 60000,
        "Invalid view " + "x " * 30000,
        "Job " + "J" * 60000 + " server action #",
        "Call from cron " + "c" * 60000,
        ("Wrong value for " + "a." * 30000),
        "Field " + "f" * 60000 + " with unknown currency_field",
    ]
    for s in evil:
        t = time.perf_counter()
        dn.match(s)
        assert time.perf_counter() - t < 0.5


def test_no_nested_quantifiers():
    for s in dn.CATALOGUE:
        assert not re.search(r"\([^()]*[+*][^()]*\)[+*{]", s.pattern)
        assert re.search(r"[+*](?!\?)", s.pattern.replace("\\+", "").replace("\\*", "")) is None


def test_tail_scanned_and_control_chars_stripped():
    big = "noise\n" * 20000 + "\x1b[31m" + SAMPLES["singleton"]
    r = dn.match(big)
    assert r.truncated and r.matches[0].id == "singleton"
    assert "\x1b" not in json.dumps(r.to_dict())


# AC5 redaction before anything is returned or stored
SECRETS = [
    "password=hunter2",
    "admin_passwd: s3cr3t",
    "Authorization: Bearer abcdefghijklmnop",
    "postgresql://odoo:pw123@db:5432/x",
    "api_key=sk-ABCDEFGH12345678",
    "token: ghp_abcdefghij1234567890",
]


@pytest.mark.parametrize("secret", SECRETS)
def test_secrets_redacted_in_evidence(secret):
    r = dn.match(f"{SAMPLES['singleton']} {secret}")
    out = json.dumps(r.to_dict())
    for bit in (
        "hunter2",
        "s3cr3t",
        "abcdefghijklmnop",
        "pw123",
        "ABCDEFGH12345678",
        "abcdefghij1234567890",
    ):
        assert bit not in out


def _note(**kw):
    n = {
        "id": "dn-new-lesson",
        "title": "New lesson",
        "sample": "SomeError: thing broke password=hunter2",
        "cause": "cause",
        "diagnosis": ["look"],
        "fix_tier": 2,
        "dont": ["do not"],
        "versions": [18],
        "source": "run 42",
    }
    n.update(kw)
    return n


# AC6 notes queue: append-only, fullmatch id, duplicates refused, whitelist, redacted, no auto-promotion
def test_notes_append_and_redact(tmp_path):
    p = tmp_path / "q.jsonl"
    rec = dn.append_note(_note(), path=p)
    assert rec["status"] == "candidate" and "hunter2" not in p.read_text()
    assert len(dn.list_notes(path=p)) == 1
    assert dn.match("SomeError: thing broke").status == "unknown"  # not auto-promoted


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "dn-ok\n"},
        {"id": "DN-UP"},
        {"id": "dn-a"},
        {"id": "xx-abc"},
        {"extra": 1},
        {"fix_tier": 4},
        {"fix_tier": True},
        {"versions": [16]},
        {"versions": ["17"]},
        {"diagnosis": "str"},
        {"title": ""},
        {"sample": "x" * 4001},
    ],
)
def test_notes_reject_bad(tmp_path, bad):
    with pytest.raises(ValueError):
        dn.append_note(_note(**bad), path=tmp_path / "q.jsonl")


def test_notes_duplicates_refused(tmp_path):
    p = tmp_path / "q.jsonl"
    dn.append_note(_note(), path=p)
    with pytest.raises(ValueError):
        dn.append_note(_note(), path=p)
    with pytest.raises(ValueError):
        dn.append_note(_note(id="dn-other"), path=p)  # same sample
    with pytest.raises(ValueError):
        dn.append_note(_note(id="dn-singleton", sample="other"), path=p)
    before = p.read_text()
    dn.append_note(_note(id="dn-third", sample="third"), path=p)
    assert p.read_text().startswith(before)  # append-only


def test_promotion_draft_needs_reviewer_and_writes_nothing(tmp_path):
    p = tmp_path / "q.jsonl"
    dn.append_note(_note(), path=p)
    with pytest.raises(PermissionError):
        dn.promotion_draft(
            "dn-new-lesson", reviewer=" ", needle="x", file_by_version={18: "f"}, path=p
        )
    with pytest.raises(ValueError):
        dn.promotion_draft("dn-new-lesson", reviewer="Tope", needle="x", file_by_version={}, path=p)
    before = p.read_text()
    d = dn.promotion_draft(
        "dn-new-lesson",
        reviewer="Tope",
        needle="thing broke",
        file_by_version={18: "odoo/x.py"},
        path=p,
    )
    assert d["reviewed_by"] == "Tope" and d["pattern"] == re.escape("thing broke")
    assert p.read_text() == before and "new-lesson" not in {s.id for s in dn.CATALOGUE}


def test_shipped_queue_is_valid_jsonl():
    for r in dn.list_notes():
        dn.check_note(r["note"])


# AC7 data-only integration; tiers from tiers.py; T3 unchanged
def test_match_returns_plain_data_with_tier_readiness():
    r = dn.match(SAMPLES["invalid-field"]).to_dict()
    m = r["matches"][0]
    assert m["fix_tier"] == tt.T3 and m["fix_tier_ready"] is tt.tier_ready(tt.T3) is False
    json.dumps(r)


def test_module_is_read_only_and_t3_off():
    src = Path(dn.__file__).read_text()
    for bad in ("subprocess", "requests", "execute(", "os.system", "eval(", "exec("):
        assert bad not in src
    assert tt.tier_ready(tt.T3) is False

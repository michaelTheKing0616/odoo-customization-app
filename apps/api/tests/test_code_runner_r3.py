import pytest

from app.code_runner import library as lib
from app.code_runner import promote as pm
from app.code_runner import testing as crt
from app.code_runner import vault


@pytest.fixture(autouse=True)
def _dir(tmp_path, monkeypatch):
    monkeypatch.setenv("INGENIUM_CODE_RUNNER_DIR", str(tmp_path))


def test_merge3_disjoint_and_conflict():
    base = "a\nb\nc\nd\n"
    assert lib.merge3(base, "A\nb\nc\nd\n", "a\nb\nc\nD\n") == "A\nb\nc\nD\n"
    assert lib.merge3(base, "a\nB1\nc\nd\n", "a\nB2\nc\nd\n") is None


def test_library_versions_live_and_comments():
    s = lib.create("w", name="One", code="x = 1\n", by="u", tags=["t"])
    r1 = lib.live_put("w", s["id"], base_rev=1, code="x = 2\n", by="u")
    assert r1["ok"] and r1["rev"] == 2
    stale = lib.live_put("w", s["id"], base_rev=1, code="x = 3\n", by="v")
    assert not stale["ok"] and stale["conflict"]
    assert lib.save_version("w", s["id"], by="u")["n"] == 2
    assert "-x = 1" in lib.diff("x = 1\n", "x = 2\n")
    c = lib.comment("w", s["id"], line=1, text="why 2?", by="v")
    assert lib.resolve_comment("w", s["id"], c["id"], reply="ok", by="u", resolved=True)["resolved"]
    found = lib.search("w", q="one")["scripts"]
    assert found[0]["versions"] == 2 and found[0]["open_comments"] == 0
    assert lib.search("w", tag="t")["tags"] == ["t"]


def test_params_detect_and_coerce():
    spec = lib.detect_params('a = params.get("limit", 50)\nb = params["partner_ids"]\nc = params.get("since")\nd = params.get("dry", True)')
    types = {f["name"]: f["type"] for f in spec}
    assert types == {"limit": "int", "partner_ids": "ids", "since": "date", "dry": "bool"}
    vals, errs = lib.coerce_params(spec, {"limit": "10", "partner_ids": "1, 2", "since": "2026-01-01"})
    assert vals["limit"] == 10 and vals["partner_ids"] == [1, 2] and vals["dry"] is True and not errs
    _, errs = lib.coerce_params(spec, {"limit": "x"})
    assert any("Limit" in e for e in errs) and any("Partner ids" in e for e in errs)


def test_vault_scoped_and_scrubbed():
    vault.put("w", "api_token", "s3cr3t-value", "u", connections=["c1"])
    assert vault.names("w")[0]["name"] == "api_token" and "v" not in vault.names("w")[0]
    assert vault.for_run("w", "c1", 'x = secret("api_token")') == {"api_token": "s3cr3t-value"}
    assert vault.for_run("w", "c2", 'x = secret("api_token")') == {}
    assert vault.for_run("w", "c1", "x = 1") == {}
    assert vault.scrub("token s3cr3t-value used", ["s3cr3t-value"]) == "token *** used"
    with pytest.raises(ValueError):
        vault.put("w", "bad name", "v", "u")


def test_promote_check_and_shim():
    assert pm.check('import os\nodoo.execute_kw("res.partner", "message_post", [[1]])\nx = secret("k")')[0].startswith("Line 1")
    assert len(pm.check('import os\nodoo.execute_kw("res.partner", "message_post", [[1]])\nx = secret("k")')) == 3
    code = pm.server_code('ids = odoo.execute_kw("res.partner", "search", [[]])\nlog(len(ids))', {"limit": 5})
    assert "_ek('res.partner', 'search', [[]])" in code and "params = {'limit': 5}" in code and "class " not in code
    compile(code, "<srv>", "exec")


def test_tests_evaluate():
    run = {"error": None, "changes": [1, 2, 3], "results": [{}], "events": [{"msg": "Updated 3"}]}
    assert crt.evaluate(run, {"max_changes": 5, "min_rows": 1, "log_contains": "Updated"}) == []
    assert len(crt.evaluate(run, {"max_changes": 2, "min_rows": 2, "log_contains": "nope"})) == 3


def test_gallery_scripts_pass_runner_rules():
    from app.code_runner.child import check_source

    for g in lib.GALLERY:
        check_source(g["code"])
        compile(g["code"], g["id"], "exec")

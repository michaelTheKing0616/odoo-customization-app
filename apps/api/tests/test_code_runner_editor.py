from app.code_runner import ai as cr_ai
from app.code_runner.lint import lint
from app.code_runner.schema import major_of, methods_for
from app.code_runner.versions import compare

FIELDS = {"res.partner": {"name": {"type": "char"}, "email": {"type": "char"}, "active": {"type": "boolean"}}}
MODELS = {"res.partner", "sale.order", "account.move"}


def run(code, major=18):
    return lint(code, major=major, model_names=MODELS, fields_of=FIELDS.get)


def test_unknown_field_with_suggestion():
    out = run('odoo.execute_kw("res.partner", "search_read", [[("emial", "=", "x")]], {"fields": ["name", "nme"]})')
    assert [(i["message"], i["fix"]) for i in out] == [("res.partner has no field 'emial'.", "email"),
                                                      ("res.partner has no field 'nme'.", "name")]


def test_unknown_model_and_write_vals():
    out = run('odoo.execute_kw("res.partnr", "search", [[]])\nodoo.execute_kw("res.partner", "write", [[1], {"emal": 1}])')
    assert out[0]["fix"] == "res.partner" and out[1]["line"] == 2 and out[1]["fix"] == "email"


def test_version_deprecations():
    assert any("name_get" in i["message"] for i in run('odoo.execute_kw("res.partner", "name_get", [[1]])', 17))
    assert not run('odoo.execute_kw("res.partner", "read_group", [[], ["name"], ["name"]])', 18)
    assert any("formatted_read_group" in i["message"] for i in run('odoo.execute_kw("res.partner", "read_group", [[], [], []])', 19))
    assert "check_access" in methods_for(18) and "check_access_rights" not in methods_for(18) and major_of("saas~18.3") == 18


def test_private_method_and_syntax():
    assert run('odoo.execute_kw("res.partner", "_compute_x", [[1]])')[0]["severity"] == "error"
    assert "can't read" in run("def (")[0]["message"]


def test_versions_compare():
    out = compare({"18": {"a": {"type": "char"}, "b": {"type": "char"}}, "17": {"a": {"type": "text"}}, "20": None})
    assert out["versions"] == ["17", "18", "20"] and out["missing_model"] == ["20"] and out["differing"] == 2


def test_ai_authorize_refuses_imports_and_flags_new_money_writes():
    lint_fn = lambda c: []  # noqa: E731
    assert not cr_ai.authorize("import os\nlog(1)", "", lint_fn)["ok"]
    assert not cr_ai.authorize("open('/etc/passwd')", "", lint_fn)["ok"]
    got = cr_ai.authorize('odoo.execute_kw("account.move", "write", [[1], {"ref": "x"}])', "log(1)", lint_fn)
    assert got["ok"] and got["money"] == ["write on account.move"]
    same = 'odoo.execute_kw("account.move", "write", [[1], {}])'
    assert cr_ai.authorize(same, same, lint_fn)["money"] == []

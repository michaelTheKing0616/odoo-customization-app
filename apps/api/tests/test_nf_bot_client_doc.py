"""BOT-CLIENT-DOC: behaviour tests (pure functions; no DB, no RPC)."""

import ast
import copy
import json
from pathlib import Path

import pytest

from app.bots import client_doc as cd

FX = Path(__file__).parent / "fixtures" / "client_doc"
SRC = Path(cd.__file__).parent


def fx(name):
    return json.loads((FX / name).read_text())


def lines(doc):
    return [ln for sec in doc["sections"].values() for ln in sec]


def qs(doc):
    return doc["sections"]["questions"]


def both(f):
    return (
        cd.clarification(f["spec"], f["review"], f["fit"], f.get("caps")),
        cd.handoff(f["spec"], f["run"], f["verify"], None, f.get("caps")),
    )


@pytest.mark.parametrize("name", ["generic.json", "industry_mfg.json"])
def test_every_line_has_source_and_docs_render(name):
    for doc in both(fx(name)):
        assert doc["writes"] == 0 and lines(doc)
        assert all(ln["source"] and ln["source"] != cd.TBC for ln in lines(doc))
        md = cd.render_markdown(doc)
        assert md.count("[source: ") == len(lines(doc))
        assert cd.render_html(doc).count("data-source=") == len(lines(doc))


def test_question_categories_and_sources():
    c, _ = both(fx("generic.json"))
    cats = {q["category"]: q["source"] for q in qs(c)}
    assert cats["conflict"] == "design:review:0"
    assert "needs-review" not in cats  # conflict on the same ref wins
    assert cats["missing-value"] == "spec:item:res.partner.category:name=Tier A"
    assert cats["low-confidence"] == "fitgap:step:s2"
    assert not any(q["source"] == "fitgap:step:s1" for q in qs(c))
    assert all(q["why"] and q["options"] and q["default"] == cd.doc.POLICY_DEFAULT for q in qs(c))
    order = [cd.doc.CATEGORIES.index(q["category"]) for q in qs(c)]
    assert order == sorted(order)


def test_needs_custom_and_other_review():
    spec = {
        "odoo_major": 17,
        "items": [
            {"ref": "x.y:k=1", "model": "x.y", "verdict": "needs-custom", "reason": "no stock fit"}
        ],
    }
    c = cd.clarification(spec, ["step s9: step produced nothing; needs review"], {"steps": []})
    assert [q["category"] for q in qs(c)] == ["needs-custom", "other-review"]
    assert "no stock fit" in qs(c)[0]["why"]


def test_blocked_for_version_wording_from_catalogue():
    c, h = both(fx("industry_mfg.json"))
    v = [q for q in qs(c) if q["category"] == "version-or-edition"]
    assert len(v) == 1 and v[0]["source"] == "caps:17:mrp.bom"
    assert "mrp" in v[0]["why"] and "install" in v[0]["why"]
    nd = [ln for ln in h["sections"]["not done"] if ln["source"].startswith("caps:")]
    assert nd and nd[0]["reason"] == v[0]["why"]
    f = fx("industry_mfg.json")
    f["caps"]["installed"].append("mrp")
    c2, _ = both(f)
    assert not [q for q in qs(c2) if q["category"] == "version-or-edition"]


def test_no_caps_context_means_no_version_claims():
    f = fx("industry_mfg.json")
    del f["caps"]
    c, h = both(f)
    assert not any(ln["source"].startswith("caps:") for ln in lines(c) + lines(h))


def test_handoff_configured_test_undo_and_not_done():
    _, h = both(fx("generic.json"))
    s = h["sections"]
    assert s["configured"][0]["check"] == "matches"
    assert s["how to test"][0]["expected"] == "color = to be confirmed, name = Tier A"
    assert s["how to test"][0]["source"] == "spec:item:res.partner.category:name=Tier A"
    assert s["undo"][0]["how"].startswith("delete the created record")
    assert s["not done"][0]["reason"] == "needs review"
    assert s["known limits"][0]["text"] == "nothing recorded"


def test_unknown_never_filled():
    f = fx("generic.json")
    del f["run"]["steps"][0]["undo"]
    f["verify"]["items"] = []
    del f["run"]["steps"][0]["verified"]
    h = cd.handoff(f["spec"], f["run"], f["verify"])
    assert h["sections"]["undo"][0]["how"] == cd.TBC
    assert h["sections"]["configured"][0]["check"] == cd.TBC
    assert "to be confirmed" in h["sections"]["known limits"][0]["text"]
    cards = [{"ref": "res.partner.category:name=Tier A", "undo_how": "archive it"}]
    h2 = cd.handoff(f["spec"], f["run"], f["verify"], cards)
    assert h2["sections"]["undo"][0]["how"] == cd.TBC  # card undo_how never used


def test_partial_input_not_provided():
    c = cd.clarification()
    h = cd.handoff()
    for sec in ("design", "design review", "fit-gap"):
        assert c["sections"][sec][0]["text"] == "not provided"
    assert {ln["source"] for ln in h["sections"]["inputs"]} == {
        "input:spec",
        "input:run",
        "input:verify",
    }
    assert h["meta"]["run_status"] == "not provided"
    cd.clarification("junk", 5, [1])  # never raises on odd input
    cd.handoff([1], "x", 3, [None])


def test_escaping_untrusted_values():
    bad = "<script>alert(1)</script> **[x](javascript:y)**\n# h"
    spec = {
        "odoo_major": 17,
        "items": [{"ref": bad, "model": "m", "verdict": "needs review", "reason": bad}],
    }
    c = cd.clarification(spec, [bad], {})
    md, ht = cd.render_markdown(c), cd.render_html(c)
    assert "<script>" not in md and "<script>" not in ht
    assert "](javascript" not in md and "**[" not in md
    assert "\n# h" not in md
    assert all("\n" not in v for ln in lines(c) for v in ln.values())


def test_deterministic_and_order_independent():
    f = fx("generic.json")
    a = both(f)
    g = copy.deepcopy(f)
    g["spec"]["items"].reverse()
    g["run"]["steps"].reverse()
    g["fit"]["steps"].reverse()
    assert both(g) == a == both(f)
    assert cd.render_markdown(a[0]) == cd.render_markdown(both(g)[0])


def test_bounded_size():
    spec = {
        "odoo_major": 17,
        "items": [
            {"ref": f"m:k={i}", "model": "m", "verdict": "needs review", "reason": "x" * 5000}
            for i in range(cd.MAX_LINES + 50)
        ],
    }
    c = cd.clarification(spec, [], {})
    assert c["truncated"] and len(lines(c)) == cd.MAX_LINES
    assert max(len(v) for ln in lines(c) for v in ln.values()) <= cd.doc.MAX_TEXT
    assert "Truncated" in cd.render_markdown(c)


def test_no_network_rpc_or_model_imports():
    banned = (
        "xmlrpc",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "odoo",
        "walker",
        "guard",
        "operator_flow",
        "configverify",
        "llm",
        "ai",
        "openai",
        "google",
    )
    for p in SRC.glob("*.py"):
        tree = ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in n.names] + [getattr(n, "module", "") or ""]
                for m in mods:
                    assert not any(part in banned for part in m.split(".")), (p, m)


def _run_step(slot, ref, status, **kw):
    return {"title": "t", "availability": "", "status": status, "ref": ref, "slot": slot} | kw


def test_undo_only_for_executed_this_session():
    spec = {"odoo_major": 17, "items": [{"ref": f"m:k={i}", "model": "m"} for i in range(3)]}
    run = {
        "steps": [
            _run_step(
                "1:m:k=0", "m:k=0", "already-done", note="x; nothing written", verified="matches"
            ),
            _run_step("2:m:k=1", "m:k=1", "executed", undo="unlink 5", resumed=True),
            _run_step("3:m:k=2", "m:k=2", "executed", undo="unlink 6"),
        ]
    }
    cards = [{"ref": "m:k=0", "undo_how": "archive it"}]
    u = [ln["how"] for ln in cd.handoff(spec, run, {}, cards)["sections"]["undo"]]
    assert u == [cd.doc.NOTHING_TO_UNDO, cd.doc.EARLIER, "unlink 6"]
    assert not any("archive" in ln for ln in u)


def _cyc():
    a = {}
    a["a"] = a
    deep = x = []
    for _ in range(5000):
        x.append([])
        x = x[0]
    return a, deep


@pytest.mark.parametrize("bad", _cyc())
def test_cyclic_and_deep_values_never_raise(bad):
    spec = {
        "odoo_major": 17,
        "items": [
            {
                "ref": bad,
                "model": "m",
                "verdict": "needs review",
                "expected": {"f": bad},
                "key": {"k": bad},
            }
        ],
    }
    run = {"steps": [_run_step(bad, bad, "executed", undo=bad)]}
    for doc in (
        cd.clarification(spec, [bad], {"steps": [{"step_id": bad}]}),
        cd.handoff(spec, run, {"items": [{"ref": bad}]}, [bad]),
    ):
        vals = [v for ln in lines(doc) for v in ln.values()]
        assert max(map(len, vals)) <= cd.doc.MAX_TEXT
        if isinstance(bad, dict):
            assert any(cd.doc.UNREADABLE in v for v in vals)
        cd.render_markdown(doc), cd.render_html(doc)


def test_control_and_format_chars_stripped():
    c = cd.clarification(None, ["a\u202eb\u200bc\x00d\x07e"], None)
    q = [x for x in qs(c) if x["category"] == "other-review"][0]["question"]
    assert q == "Please resolve: abcde"
    assert "\u202e" not in cd.render_markdown(c) + cd.render_html(c)


def test_renderers_tolerate_odd_documents():
    odd = {"doc": "x", "meta": {1: 2}, "sections": {"s": [None, "str", {"a": 1}], "t": 5}}
    md, ht = cd.render_markdown(odd), cd.render_html(odd)
    assert md.count("[source: ") == 1 and ht.count("data-source") == 1


def test_duplicate_refs_deterministic_and_questioned():
    it = [{"ref": "m:k=1", "model": "m", "verdict": "needs review", "reason": r} for r in "ab"]
    spec = {"odoo_major": 17, "items": it}
    a = cd.clarification(spec, [], {})
    b = cd.clarification(spec | {"items": it[::-1]}, [], {})
    assert a == b and cd.render_markdown(a) == cd.render_markdown(b)
    assert [q["category"] for q in qs(a)].count("duplicate-ref") == 1
    run = {"steps": [_run_step("1:m:k=1", "m:k=1", "blocked", reason=r) for r in "ab"]}
    assert cd.handoff(spec, run, {}) == cd.handoff(spec, {"steps": run["steps"][::-1]}, {})


def test_conflict_wins_over_needs_review_and_needs_human_low_confidence():
    spec = {"items": [{"ref": "m:k=1", "model": "m", "verdict": "needs review"}]}
    c = cd.clarification(
        spec,
        ["conflict on m:k=1: value f = 1 vs 2"],
        {"steps": [{"step_id": "s", "match_confidence": "strong pattern", "needs_human": True}]},
    )
    assert [q["category"] for q in qs(c)] == ["conflict", "low-confidence"]


def test_slots_sort_numerically():
    run = {"steps": [_run_step(f"{n}:m:k={n}", f"m:k={n}", "blocked", reason="r") for n in (10, 2)]}
    nd = cd.handoff({"items": []}, run, {})["sections"]["not done"]
    assert [ln["ref"] for ln in nd[:2]] == ["m:k=2", "m:k=10"]


def test_real_module_shapes_end_to_end():
    from app.bots import operator_flow as of
    from app.bots.fitgap import fitgap as fg
    from app.bots.fitgap import ingest
    from app.bots.process_design import design as pd

    g = ingest.parse_text("1. Move the deal to qualified in the sales pipeline\n2. Zorp the flux")
    fit = fg.classify(g, fg.OdooEnv.from_modules(17, {"base", "crm"}, set()))
    desc = {"steps": [{"id": s.step_id, "name": s.text} for s in fit.steps]}
    dd = pd.design(desc, fit=fit).to_dict()
    refs = [i["ref"] for i in dd["items"]]
    assert refs
    cards = [
        of.StepCard(
            n=n, ref=r, kind="record", model="m", title="t", undo_how="archive it"
        ).to_dict()
        for n, r in enumerate(refs, 1)
    ]
    steps = [
        _run_step(
            cards[0]["slot"],
            refs[0],
            "already-done",
            note="x; nothing written",
            by="op",
            verified="matches",
        )
    ]
    steps += [
        _run_step(
            c["slot"],
            c["ref"],
            "executed",
            record_ids=[1],
            undo="unlink 1",
            by="op",
            replayed=False,
            verified="differs",
            needs_review="after the run the check says differs",
        )
        for c in cards[1:]
    ]
    run = {
        "plan_id": "p",
        "status": "attention",
        "counts": {"executed": len(steps) - 1},
        "steps": steps,
        "verify": "attention",
    }
    c = cd.clarification(
        dd, dd["review"], fit.to_dict(), {"edition": "community", "installed": ["base"]}
    )
    h = cd.handoff(dd, run, {"items": []}, cards, {"edition": "community", "installed": ["base"]})
    for doc in (c, h):
        assert all(ln["source"] for ln in lines(doc))
    assert h["sections"]["undo"][0]["how"] == cd.doc.NOTHING_TO_UNDO
    assert not any(ln["how"] == "archive it" for ln in h["sections"]["undo"])


def test_conflict_matches_longest_exact_ref():
    spec = {
        "items": [
            {"ref": "m:name=a", "model": "m", "verdict": "needs review", "reason": "own"},
            {"ref": "m:name=a: b", "model": "m", "verdict": "needs review"},
        ]
    }
    c = cd.clarification(spec, ["conflict on m:name=a: b: value k = 1 vs 2"], {})
    got = {(q["category"], q["source"]) for q in qs(c)}
    assert ("conflict", "design:review:0") in got
    assert ("needs-review", "spec:item:m:name=a") in got
    assert ("needs-review", "spec:item:m:name=a: b") not in got
    c2 = cd.clarification(spec, ["conflict on zz: value k"], {})
    assert [q["category"] for q in qs(c2)].count("needs-review") == 2


class Boom:
    def __str__(self):
        raise RuntimeError("x")

    __repr__ = __str__


def test_failing_str_never_escapes():
    b = Boom()
    item = {
        "ref": b,
        "model": "m",
        "verdict": "needs review",
        "expected": {"f": b},
        "key": {"k": b},
    }
    spec = {"odoo_major": b, "items": [item]}
    run = {
        "counts": {"executed": b},
        "steps": [_run_step("1:x", b, "executed", undo=b)],
        "status": b,
        "plan_id": b,
    }
    for doc in (
        cd.clarification(spec, [b], {"steps": [{"step_id": b, "text": b}]}, {"edition": b}),
        cd.clarification(
            {"odoo_major": 17, "items": [item]}, [], {}, {"edition": "community", "installed": [b]}
        ),
        cd.handoff(
            spec,
            run,
            {"items": [{"ref": b, "status": b}], "company_view": b},
            [b],
            {"edition": "community", "installed": b},
        ),
    ):
        cd.render_markdown(doc), cd.render_html(doc)
        assert any(cd.doc.UNREADABLE in v for ln in lines(doc) for v in ln.values())


@pytest.mark.parametrize(
    "odd",
    [
        None,
        "s",
        [1],
        {"sections": "x"},
        {"doc": [1], "meta": "m"},
        {"sections": {"a": [1, None, {"k": Boom(), "source": Boom()}]}},
    ],
)
def test_renderers_never_raise(odd):
    assert cd.render_markdown(odd).startswith("# ")
    assert cd.render_html(odd).startswith("<h1>")


def test_zwj_only_between_emoji():
    fam = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
    c = cd.clarification(None, [f"a\u202eb\u200bc\u200dd {fam}"], None)
    q = [x for x in qs(c) if x["category"] == "other-review"][0]["question"]
    assert q == f"Please resolve: abcd {fam}"

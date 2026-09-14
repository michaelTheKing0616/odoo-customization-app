"""Gold CBN currency rates — classify, seed, zip. No x_* FX app."""

from __future__ import annotations

import io
import zipfile

from app.ai_elite import run_elite_quality_pass
from app.ai_generation_engine import (
    classify_generation,
    is_gold_option_a_draft,
    maybe_seed_from_capability,
)
from app.ai_operator_brief import is_cbn_currency_rates_prompt
from app.ai_pipeline import seed_studio_draft
from app.ai_structural_zip_gate import structural_zip_gate
from app.custom_code_authoring import lint_custom_code_blocks, lint_python
from app.module_spec_codec import export_draft_module_zip
from app.option_a_templates import apply_gold_template


CBN_PROMPT = (
    "Company currency NGN. Activate USD, GBP, and EUR. "
    "Add Central Bank of Nigeria as the Service on Automatic Currency Rates "
    "so the cron pulls live CBN rates."
)
NIGERIA_AUTOPILOT = (
    "We are a company in Lagos, Nigeria. Stand up Community Accounting. "
    "Company currency NGN. Custom residual: None. Capability path: stock_first."
)


def test_cbn_prompt_detects_and_nigeria_autopilot_does_not() -> None:
    assert is_cbn_currency_rates_prompt(CBN_PROMPT) is True
    assert is_cbn_currency_rates_prompt(NIGERIA_AUTOPILOT) is False
    assert is_cbn_currency_rates_prompt("activate NGN for Nigeria") is False


def test_cbn_prompt_selects_gold_not_fx_app() -> None:
    plan = classify_generation(CBN_PROMPT)
    assert plan.capability == "option_a_standalone"
    assert plan.gold_artifact_id == "currency_rate_cbn"
    assert plan.module_delivery is True
    assert "x_*" in plan.honesty or "x_* FX" in plan.honesty

    draft = maybe_seed_from_capability(CBN_PROMPT)
    assert draft is not None
    assert is_gold_option_a_draft(draft)
    assert draft.get("technical_name") == "currency_rate_cbn"
    assert "account" in (draft.get("depends") or [])
    assert "currency_rate_live" not in (draft.get("depends") or [])
    models = [str(m.get("model")) for m in draft.get("models") or []]
    assert "x_fx" not in models
    assert "x_exchange" not in models
    assert "res.company" in models
    ir = draft["_generation_engine"]
    assert ir["gold_artifact_id"] == "currency_rate_cbn"
    assert ir.get("option_a_settings", {}).get("model") == "res.company"

    seeded = seed_studio_draft(CBN_PROMPT)
    assert seeded.get("technical_name") == "currency_rate_cbn"
    assert seeded.get("domain_pack") not in {"restaurant", "retail_supermarket"}


def test_cbn_prompt_does_not_match_purchase_request_pack() -> None:
    from app.ai_conversation.intent_gate import thin_document_brief
    from app.ai_domain_packs import match_domain_pack

    assert match_domain_pack(CBN_PROMPT) is None
    assert thin_document_brief(CBN_PROMPT) is False


def test_refine_cbn_on_purchase_request_is_refused() -> None:
    from app.ai_conversation.refine import apply_refinement
    from app.ai_domain_pack_purchase_request import purchase_request_pack

    pack = purchase_request_pack()
    result = apply_refinement(pack, CBN_PROMPT)
    assert result["ok"] is False
    assert "Option A" in str(result.get("error") or "")
    assert result["draft"].get("display_name") == pack.get("display_name")


def test_nigeria_stock_first_is_not_cbn_gold() -> None:
    plan = classify_generation(NIGERIA_AUTOPILOT)
    assert plan.gold_artifact_id != "currency_rate_cbn"
    assert plan.capability == "stock_reuse"
    draft = maybe_seed_from_capability(NIGERIA_AUTOPILOT)
    assert draft is not None
    assert draft.get("technical_name") != "currency_rate_cbn"


def test_cbn_gold_zip_has_provider_and_no_x_fx() -> None:
    from app.sandbox import sandbox_major_for_connection

    draft = apply_gold_template(CBN_PROMPT, "currency_rate_cbn")
    lint = lint_custom_code_blocks(draft)
    assert lint["ok"] is True, lint
    zip_bytes = export_draft_module_zip(
        draft, odoo_major=sandbox_major_for_connection("19.0")
    )
    gate = structural_zip_gate(zip_bytes)
    assert gate["ok"] is True, gate["findings"]
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        blob = {n: zf.read(n).decode("utf-8", errors="replace") for n in names}
    assert any(n.endswith("models/cbn_rates.py") for n in names)
    assert any(n.endswith("tests/test_currency_rate_cbn.py") for n in names)
    py = next(v for k, v in blob.items() if k.endswith("models/cbn_rates.py"))
    assert "GetAllExchangeRatesGRAPH" in py
    assert "Central Bank of Nigeria" in "\n".join(blob.values())
    assert "_name = 'x_fx'" not in py
    assert "currency_rate_live" not in blob.get(
        next(n for n in names if n.endswith("__manifest__.py")), ""
    )


def test_elite_does_not_overwrite_gold_cbn_tests() -> None:
    draft = apply_gold_template(CBN_PROMPT, "currency_rate_cbn")
    before = {
        str(b.get("source_file")): str(b.get("content"))
        for b in draft.get("custom_code_blocks") or []
        if isinstance(b, dict)
    }
    run_elite_quality_pass(draft)
    gold = next(
        b
        for b in draft["custom_code_blocks"]
        if b.get("source_file") == "tests/test_currency_rate_cbn.py"
    )
    assert gold["content"] == before["tests/test_currency_rate_cbn.py"]


def test_lint_allows_urllib_json_not_os() -> None:
    allowed = lint_python(
        "import json\nfrom urllib.request import urlopen\nurlopen\njson.loads\n"
    )
    assert not any(i["code"] == "import_forbidden" for i in allowed)
    blocked = lint_python("import os\nos.listdir('.')\n")
    assert any(i["code"] == "import_forbidden" for i in blocked)


def test_cbn_prove_success_includes_zip_bytes(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.ai_option_a_quality import prove_option_a_in_sandbox

    draft = apply_gold_template(CBN_PROMPT, "currency_rate_cbn")

    def fake_install(*_a, **_k):
        return SimpleNamespace(
            ok=True,
            module="currency_rate_cbn",
            message="installed",
            log_tail="",
            job_id=None,
        )

    monkeypatch.setattr("app.sandbox.run_sandbox_install", fake_install)
    out = prove_option_a_in_sandbox(draft, odoo_major=19)
    assert out["ok"] is True
    assert isinstance(out.get("zip_bytes"), bytes)
    assert out["zip_bytes"][:2] == b"PK"


def test_stamp_option_a_promote_token_pops_bytes() -> None:
    from unittest.mock import MagicMock, patch

    from app.promote import stamp_option_a_promote_token

    row = MagicMock()
    row.id = "val-abc"
    result = {
        "ok": True,
        "draft": {"technical_name": "currency_rate_cbn"},
        "zip_bytes": b"PK\x03\x04fake",
    }
    with patch("app.promote.record_sandbox_validation", return_value=row):
        out = stamp_option_a_promote_token(
            MagicMock(), connection_id="c1", result=result
        )
    assert "zip_bytes" not in out
    assert out["validation_id"] == "val-abc"
    assert out["promote_ready"] is True
    assert out["module"] == "currency_rate_cbn"
    assert out["zip_base64"]

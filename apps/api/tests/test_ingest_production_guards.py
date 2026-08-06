"""Production guards — opening TB, CoA align, inventory block, notify modes, VAT."""

from __future__ import annotations

from typing import Any

from app.ingest.coa_align import align_coa_table
from app.ingest.commit import rpc_context_for_notify, run_commit_plan
from app.ingest.map import map_batch
from app.ingest.opening_balance import commit_opening_tb, validate_opening_tb_table
from app.ingest.order import build_plan
from app.ingest.schema import IngestBatch, IngestFile, IngestRow, IngestTable
from app.ingest.vat_check import format_ok


class FakeAcctClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.accounts = {
            "1000": {"id": 1, "code": "1000", "name": "Cash", "account_type": "asset_cash"},
            "2000": {"id": 2, "code": "2000", "name": "Payable", "account_type": "liability"},
        }
        self.journals = [{"id": 9, "name": "Opening", "code": "OPEN", "type": "general"}]

    def model_exists(self, model: str) -> bool:
        return model in {
            "account.account",
            "account.move",
            "account.journal",
            "res.partner",
            "uom.uom",
            "product.template",
            "stock.quant",
        }

    def list_installed_modules(self, name_prefix: str = "", limit: int = 100) -> list[Any]:
        class M:
            name = "l10n_us"

        return [M()] if name_prefix.startswith("l10n") else []

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        kwargs = kwargs or {}
        if model == "account.journal" and method == "search_read":
            return list(self.journals)
        if model == "account.account" and method == "search_read":
            domain = args[0] if args else []
            if not domain:
                return list(self.accounts.values())
            # [('code','=',x)]
            if domain and domain[0][0] == "code" and domain[0][1] == "=":
                code = domain[0][2]
                row = self.accounts.get(code)
                return [row] if row else []
            if domain and domain[0][0] == "code":
                code = str(domain[0][2]).lower()
                return [r for c, r in self.accounts.items() if code in c.lower()][:2]
            return list(self.accounts.values())
        if model == "account.move" and method == "create":
            vals = args[0]
            self.created.append(vals)
            return 55
        if model == "ir.model.fields" and method == "search_read":
            return [
                {"name": "code", "ttype": "char", "required": True, "readonly": False},
                {"name": "name", "ttype": "char", "required": True, "readonly": False},
            ]
        if model == "res.company":
            return [{"country_id": [1, "US"]}]
        if model == "res.country":
            return [{"code": "US"}]
        if method == "search":
            return []
        return []


def test_vat_format() -> None:
    assert format_ok("IE1234567T")
    assert not format_ok("123")


def test_notify_modes() -> None:
    assert rpc_context_for_notify("batch_summary")["mail_notrack"] is True
    assert rpc_context_for_notify("individual") is None


def test_opening_tb_requires_accounts_and_creates_draft() -> None:
    client = FakeAcctClient()
    table = IngestTable(
        id="tb1",
        model="account.move",
        doc_type="opening_trial_balance",
        mapping={"code": "code", "debit": "debit", "credit": "credit"},
        rows=[
            IngestRow(raw={"code": "1000", "debit": "100", "credit": "0"}),
            IngestRow(raw={"code": "2000", "debit": "0", "credit": "100"}),
        ],
    )
    gaps, warns = validate_opening_tb_table(client, table)
    assert not gaps
    assert any("DRAFT" in w for w in warns)
    res = commit_opening_tb(client, table, dry_run=False)
    assert res["ok"] is True
    assert res["move_id"] == 55
    assert client.created[0]["move_type"] == "entry"
    assert "action_post" not in str(client.created)


def test_opening_tb_unbalanced_fails() -> None:
    client = FakeAcctClient()
    table = IngestTable(
        id="tb1",
        model="account.move",
        doc_type="opening_trial_balance",
        rows=[IngestRow(raw={"code": "1000", "debit": "50", "credit": "0"})],
    )
    validate_opening_tb_table(client, table)
    res = commit_opening_tb(client, table, dry_run=False)
    assert res["ok"] is False
    assert "balanced" in res["message"].lower()


def test_inventory_count_gaps_when_product_missing() -> None:
    client = FakeAcctClient()
    batch = IngestBatch(
        files=[IngestFile(id="f1", filename="inv.csv", doc_type="inventory_count")],
        tables=[
            IngestTable(
                id="q1",
                model="stock.quant",
                doc_type="inventory_count",
                rows=[IngestRow(raw={"product": "X", "qty": "1"})],
            )
        ],
    )
    out = map_batch(client, batch)
    assert any("product" in g.message.lower() for g in out.gaps)


def test_coa_remap_suggest_and_apply() -> None:
    from app.ingest.coa_align import apply_coa_remap, suggest_coa_remaps

    client = FakeAcctClient()
    table = IngestTable(
        id="c1",
        model="account.account",
        doc_type="coa",
        rows=[
            IngestRow(raw={"code": "9999", "name": "Cash", "account_type": "asset_cash"}),
        ],
    )
    sug = suggest_coa_remaps(client, table, min_score=0.1)
    assert sug
    assert sug[0]["suggested_code"] in {"1000", "2000"}
    notes = apply_coa_remap(table, {"9999": "1000"}, live=client.accounts)
    assert notes
    assert table.rows[0].values["code"] == "1000"


def test_coa_align_flags_legacy_codes() -> None:
    client = FakeAcctClient()
    table = IngestTable(
        id="c1",
        model="account.account",
        doc_type="coa",
        rows=[
            IngestRow(raw={"code": "1000", "name": "Cash"}),
            IngestRow(raw={"code": "9999", "name": "Legacy"}),
        ],
    )
    gaps, warns, summary = align_coa_table(client, table, allow_as_is=False)
    assert "9999" in summary["legacy_only"]
    assert any(g.value == "9999" for g in gaps)
    gaps2, _, _ = align_coa_table(client, table, allow_as_is=True)
    assert not any(g.value == "9999" for g in gaps2)


def test_commit_plan_uses_opening_path_not_generic_move() -> None:
    client = FakeAcctClient()
    batch = IngestBatch(
        notify_mode="batch_summary",
        tables=[
            IngestTable(
                id="tb1",
                model="account.move",
                doc_type="opening_trial_balance",
                rows=[
                    IngestRow(raw={"code": "1000", "debit": "10", "credit": "0"}),
                    IngestRow(raw={"code": "2000", "debit": "0", "credit": "10"}),
                ],
            )
        ],
    )
    batch.plan = build_plan(batch)
    # clear gaps from plan that reference unresolved — build_plan may copy batch gaps
    batch.gaps = []
    if batch.plan:
        batch.plan.gaps = []
    validate_opening_tb_table(client, batch.tables[0])
    log = run_commit_plan(client, batch, dry_run=True, notify_mode="batch_summary")
    assert log.created >= 1
    assert any("opening" in m.lower() or "DRAFT" in m for m in log.messages)

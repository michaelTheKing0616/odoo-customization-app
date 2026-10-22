from app.expert.nl_search import find_records, nl_search


class _Client:
    def __init__(self):
        self.calls = []

    def execute_kw(self, model, method, args, kwargs):
        self.calls.append((model, method))
        assert method == "name_search"
        if model == "res.partner":
            return [[7, "Azure Interior"]]
        if model == "sale.order":
            raise RuntimeError("no access")
        return []


def test_find_records_only_reads_and_links_to_odoo() -> None:
    c = _Client()
    recs = find_records(c, "azure", base_url="https://x.odoo.com/", available={"res.partner", "sale.order"})
    assert {m for m, _ in c.calls} == {"res.partner", "sale.order"}
    assert recs == [{"model": "res.partner", "id": 7, "name": "Azure Interior", "kind": "Contact", "href": "https://x.odoo.com/web#id=7&model=res.partner&view_type=form"}]
    hits = nl_search("azure", connection_id="c1", records=recs).hits
    assert hits[0].kind == "record" and hits[0].label == "Azure Interior"


def test_short_query_skips_record_search() -> None:
    c = _Client()
    assert find_records(c, "a", base_url="") == []
    assert c.calls == []

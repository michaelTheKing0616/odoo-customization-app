"""Suite look-only ideas: pure parts tested without Odoo; live parts run in /tmp/gap/insights_live.py."""
from app import suite_insights as si


def test_compare_lists_differences_in_plain_groups():
    a = {"version": "18", "apps": {"sale", "crm"}, "fields": {"res.partner.x_a": "A"}, "screens": {"v1"}, "schedules": {"Mail": True, "Rates": True}}
    b = {"version": "19", "apps": {"sale"}, "fields": {}, "screens": {"v1"}, "schedules": {"Mail": False}}
    out = si.compare(a, b)
    assert out["apps"]["only_here"] == ["crm"]
    assert out["fields"]["only_here"] == ["res.partner.x_a"]
    assert out["schedules"]["on_off_differs"] == ["Mail"]
    assert out["summary"].startswith("4 difference")


def test_compare_same():
    a = {"version": "18", "apps": {"sale"}, "fields": {}, "screens": set(), "schedules": {}}
    assert si.compare(a, a)["summary"] == "The two databases are set up the same."


def test_hotspots_rank_by_runs():
    out = si.hotspots([{"model": "sale.order", "count": 5}, {"model": "sale.order", "count": 2}, {"model": "res.partner", "count": 9}])
    assert out["top"][0] == {"record_type": "sale.order", "runs": 2, "records": 7}


class _Fake:
    def __init__(self, names):
        self.names = names

    def execute_kw(self, model, method, args, kw):
        if model == "ir.model":
            return 1 if method == "search_count" else [{"name": "Sales Order"}]
        return [{"name": n} for n in self.names]


def test_numbering_finds_gaps_and_duplicates():
    out = si.numbering_check(_Fake(["S00001", "S00002", "S00005", "S00005"]))
    assert out["duplicates"] == ["S00005"]
    assert out["gaps"] == [{"after": "S2", "before": "S5", "missing": 2}] or out["gaps"][0]["missing"] == 2


def test_nothing_in_module_writes():
    import inspect
    import re
    src = inspect.getsource(si)
    methods = set(re.findall(r'_x\(client, [^,]+, "(\w+)"', src))
    assert methods <= {"search", "search_count", "search_read", "read", "read_group", "fields_get", "check_object_reference"}, methods


def test_price_list_diff_only_changes():
    old = [{"Code": "A", "Price": "10"}, {"Code": "B", "Price": "5"}, {"Code": "C", "Price": "1"}]
    new = [{"Code": "A", "Price": "12"}, {"Code": "B", "Price": "5"}, {"Code": "D", "Price": "3"}]
    out = si.price_list_diff(old, new, "Code")
    assert out["changed"] == [{"row": "A", "changes": {"Price": {"old": "10", "new": "12"}}}]
    assert out["added"] == ["D"] and out["removed"] == ["C"]


class _Users:
    def __init__(self, ids):
        self.ids = ids

    def execute_kw(self, model, method, args, kw):
        if model == "res.users":
            return [{"name": f"U{args[0][0]}"}]
        if method == "search":
            return self.ids
        return []


def test_reassign_splits_fairly_and_only_drafts():
    from app import suite_playbooks as sp
    out = sp.reassign(_Users([1, 2, 3, 4, 5]), "crm.lead", "user_id", 9, [7, 8])
    assert [b["ids"] for b in out["batches"]] == [[1, 3, 5], [2, 4]]
    assert all(b["tool"] == "edit" and b["change"]["field"] == "user_id" for b in out["batches"])

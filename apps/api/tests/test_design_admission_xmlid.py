from app.design_admission import find_by_xmlid, requirement_xmlid, tag_xmlid


class FakeClient:
    def __init__(self):
        self.imd, self.autos, self.next = [], {7}, 100

    def execute_kw(self, model, method, args, kw):
        if model == "ir.model.data":
            dom = dict((d[0], d[2]) for d in args[0]) if method in {"search", "search_read"} else {}
            hits = [r for r in self.imd if all(r.get(k) == v for k, v in dom.items())]
            if method == "search_read":
                return hits[:1]
            if method == "search":
                return [r["id"] for r in hits]
            if method == "unlink":
                self.imd = [r for r in self.imd if r["id"] not in args[0]]
                return True
            if method == "create":
                self.next += 1
                self.imd.append(dict(args[0], id=self.next))
                return self.next
        if model == "base.automation" and method == "search":
            return [i for i in self.autos if i == args[0][0][2]]
        raise AssertionError((model, method))


def test_xmlid_is_stable_and_sanitized():
    assert requirement_xmlid("ingenium_req_R-3") == "ingenium.ingenium_req_r_3"
    assert requirement_xmlid("ingenium_req_R-3", 1) == "ingenium.ingenium_req_r_3_2"
    assert requirement_xmlid("") == ""


def test_tag_then_find_and_dangling_tag_is_ignored_and_replaced():
    c, x = FakeClient(), requirement_xmlid("ingenium_req_r1")
    assert find_by_xmlid(c, x, "base.automation") is None
    tag_xmlid(c, x, "base.automation", 7)
    assert find_by_xmlid(c, x, "base.automation") == 7
    c.autos.clear()  # record deleted in Odoo: tag dangles
    assert find_by_xmlid(c, x, "base.automation") is None
    c.autos.add(9)
    tag_xmlid(c, x, "base.automation", 9)
    assert len(c.imd) == 1 and find_by_xmlid(c, x, "base.automation") == 9

"""BOT-LOCKOUT-SIM: simulated post-change access; permanent adversarial cases (17 and 20)."""

from __future__ import annotations

import copy as cp
from typing import Any

import pytest

from app.bots import guard as gd
from app.bots import lockout as lk
from app.bots.risk import rules
from app.bots.risk.rules import Refusal
from tests.test_nf_bot_clone import gate  # noqa: F401
from tests.test_nf_bot_kill_audit import OWNER, engine  # noqa: F401

BOT = 10
M2M = {"type": "many2many", "relation": "res.groups", "store": True}


class Fake:
    """In-memory Odoo access model; `v` 17 (groups_id/users) or 20 (group_ids/user_ids)."""

    def __init__(self, v: int = 17) -> None:
        self.v, self.calls, self.fail = v, [], set()
        self.groups = {
            1: ("Internal User", []),
            2: ("Settings", [3, 1]),
            3: ("Access Rights", [1]),
            4: ("Portal", []),
            5: ("Sales / User", [1]),
            6: ("Sales / Manager", [5]),
        }
        self.users = {
            2: dict(name="Admin", login="admin", groups={2}, share=False, c=[1], cid=1),
            BOT: dict(name="Bot", login="bot", groups={2}, share=False, c=[1], cid=1),
            11: dict(name="Alice", login="alice", groups={6}, share=False, c=[1], cid=1),
            12: dict(name="Pete", login="pete", groups={4}, share=True, c=[1], cid=1),
            14: dict(name="Dana", login="dana", groups={5}, share=False, c=[2], cid=2),
        }
        self.oauth: dict[int, int] = {}
        self.acl = [
            dict(
                id=1,
                model_id=[100, "sale.order"],
                group_id=[5, "x"],
                active=True,
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=False,
            ),
            dict(
                id=2,
                model_id=[101, "res.partner"],
                group_id=[1, "x"],
                active=True,
                perm_read=True,
                perm_write=False,
                perm_create=False,
                perm_unlink=False,
            ),
        ]
        self.rules = [
            dict(
                id=1,
                name="sale company",
                model_id=[100, "s"],
                groups=[5],
                active=True,
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=True,
            )
        ]
        self.menus = {500: [5]}
        self.keys = {7: BOT, 8: 2}
        self.params = {1: "auth_signup.reset_password", 2: "sale.default_x"}
        self.all_override: dict[int, list[int]] = {}

    @property
    def gf(self) -> str:
        return "group_ids" if self.v >= 19 else "groups_id"

    def _closure(self, gs: set[int]) -> list[int]:
        seen, st = set(), list(gs)
        while st:
            g = st.pop()
            if g not in seen:
                seen.add(g)
                st += self.groups[g][1]
        return sorted(seen)

    def __call__(self, model: str, method: str, args: list, kw: dict) -> Any:
        self.calls.append((model, method))
        if model in self.fail:
            raise RuntimeError("AccessError")
        if method not in ("fields_get", "search_read", "read"):
            raise AssertionError(f"write attempted: {method}")
        if method == "fields_get":
            return self._meta(model)
        if model == "res.users":
            out = []
            for i, u in self.users.items():
                r = {
                    "id": i,
                    "name": u["name"],
                    "login": u["login"],
                    "active": u.get("active", True),
                    "share": u["share"],
                    self.gf: sorted(u["groups"]),
                    "company_ids": u["c"],
                    "company_id": [u["cid"], "c"],
                    "oauth_provider_id": self.oauth.get(i, False),
                }
                if self.v >= 19:
                    r["all_group_ids"] = self.all_override.get(i, self._closure(u["groups"]))
                out.append(r)
            return out
        if model == "res.groups":
            return [
                {"id": g, "name": n, "full_name": n, "implied_ids": imp}
                for g, (n, imp) in self.groups.items()
            ]
        if model == "ir.model.data":
            names = dict(group_system=2, group_erp_manager=3, group_user=1, group_portal=4)
            return [{"name": n, "res_id": r} for n, r in names.items()]
        if model == "ir.model":
            return [
                {"model": m}
                for m in (("ir.access",) if self.v >= 20 else ("ir.model.access", "ir.rule"))
            ]
        if model == "ir.access":
            let = {"perm_read": "r", "perm_write": "u", "perm_create": "c", "perm_unlink": "d"}
            rows = [
                {
                    "id": r["id"],
                    "model_id": r["model_id"],
                    "group_id": r["group_id"],
                    "active": r["active"],
                    "domain": False,
                    "operation": "".join(c for p, c in let.items() if r[p]),
                }
                for r in self.acl
            ]
            return rows + [
                {
                    "id": 9,
                    "model_id": [100, "s"],
                    "group_id": [5, "x"],
                    "active": True,
                    "domain": "[('company_id', 'in', company_ids)]",
                    "operation": "rucd",
                }
            ]
        if model == "ir.model.access":
            return cp.deepcopy(self.acl)
        if model == "ir.rule":
            return cp.deepcopy(self.rules)
        ids = args[0]
        if model == "ir.ui.menu":
            return [{"id": i, self.gf: self.menus[i]} for i in ids if i in self.menus]
        if model == "res.users.apikeys":
            return [{"id": i, "user_id": [self.keys[i], "u"]} for i in ids if i in self.keys]
        if model == "ir.config_parameter":
            return [{"id": i, "key": self.params[i]} for i in ids if i in self.params]
        return [{"id": i} for i in ids]

    def _meta(self, model: str) -> dict:
        if model == "res.users":
            m = {
                self.gf: M2M,
                "login": {"type": "char"},
                "active": {"type": "boolean"},
                "share": {"type": "boolean"},
                "name": {"type": "char"},
                "lang": {"type": "selection"},
                "company_ids": {"type": "many2many", "relation": "res.company"},
                "company_id": {"type": "many2one", "relation": "res.company"},
                "password": {"type": "char", "store": False},
                "oauth_provider_id": {"type": "many2one", "relation": "auth.oauth.provider"},
            }
            if self.v >= 19:
                m["all_group_ids"] = {**M2M, "store": False}
                m["role"] = {"type": "selection", "store": False}  # 19/20: inverse sets groups
            else:
                m["in_group_2"] = {"type": "boolean", "store": False}
                m["sel_groups_2_3"] = {"type": "selection", "store": False}
            return m
        if model == "res.groups":
            return {
                "implied_ids": M2M,
                "name": {"type": "char"},
                "full_name": {"type": "char"},
                ("user_ids" if self.v >= 19 else "users"): {
                    "type": "many2many",
                    "relation": "res.users",
                },
            }
        return {
            f: {"type": "many2many" if f.endswith("ids") or f == "groups" else "boolean"}
            for f in (
                "active",
                "groups",
                "group_ids",
                "groups_id",
                "enabled",
                "perm_read",
                "perm_write",
                "perm_create",
                "perm_unlink",
                "value",
                "smtp_host",
                "operation",
                "domain",
                "group_id",
                "model_id",
                "name",
                "domain_force",
            )
        }


def sim(f: Fake, *chs: lk.Change, bot: int = BOT):
    return lk.simulate(f, list(chs), bot_uid=bot)


def W(model: str, ids, **vals) -> lk.Change:  # noqa: N802
    return lk.Change(model, "write", tuple(ids), vals)


def refused(r, part: str) -> bool:
    return isinstance(r, Refusal) and r.rule == "RF-R8" and part in r.reason


V = pytest.mark.parametrize("v", [17, 20])


def _g(v: int) -> str:
    return "group_ids" if v >= 19 else "groups_id"


# ---------------------------------------------------------------- scope + drift
def test_every_r8_model_has_a_handler_or_a_reason():
    r8 = {m for m, fl in rules.MODEL_FLOOR.items() if fl[0] == "R8"}
    assert r8 - set(lk.HANDLERS) - set(lk.NOT_LOCKOUT) == set()
    assert not set(lk.HANDLERS) & set(lk.NOT_LOCKOUT)
    assert all(len(why) > 15 for why in lk.NOT_LOCKOUT.values())


def test_auth_sensitive_models_are_simulated():
    auth = {
        m
        for m in rules.SENSITIVE_MODELS
        if m.startswith("auth.") or "ldap" in m or m == "ir.mail_server"
    }
    assert auth and auth - set(lk.HANDLERS) == set()


def test_scope_follows_risk_layer():
    assert lk.needs_simulation("res.users", ["groups_id"])
    assert lk.needs_simulation("ir.rule", None)
    assert lk.needs_simulation("ir.cron", ["groups_id"])
    assert not lk.needs_simulation("base.automation", ["code"])
    assert not lk.needs_simulation("res.partner", ["name"])


# ---------------------------------------------------------------- adversarial (permanent)
@V
def test_last_admin_removal_refused(v):
    f = Fake(v)
    assert refused(sim(f, W("res.users", [2], **{_g(v): [(3, 2)]})), "no working admin")
    assert refused(sim(f, W("res.users", [2], active=False)), "no working admin")
    assert refused(sim(f, W("res.users", [2], login="x")), "no working admin")
    assert refused(
        sim(f, W("res.groups", [2], **{("user_ids" if v >= 19 else "users"): [(3, 2)]})),
        "no working admin",
    )


@V
def test_bot_admin_does_not_count_and_second_admin_allows_l3(v):
    f = Fake(v)
    f.users[2]["groups"] = {3}  # only the Bot holds Settings
    assert refused(sim(f, W("res.users", [11], lang="fr_FR")), "even now")
    f = Fake(v)
    f.users[15] = dict(name="Eve", login="eve", groups={2}, share=False, c=[1], cid=1)
    r = sim(f, W("res.users", [2], **{_g(v): [(3, 2)]}))
    assert isinstance(r, lk.LockoutSim) and r.tier == 3 and r.admins_after == 1
    assert any("loses Settings" in x for i in r.impacts if i.user_id == 2 for x in i.lines)
    assert r.gate_facts() == {"admins_after": 1, "removes_bot_access": False}


@V
def test_circular_implied_groups_refused_and_terminates(v):
    r = sim(Fake(v), W("res.groups", [1], implied_ids=[(4, 6)]))
    assert refused(r, "circular")


@V
def test_portal_to_internal_reported(v):
    r = sim(Fake(v), W("res.users", [12], **{_g(v): [(6, 0, [1])]}))
    assert isinstance(r, lk.LockoutSim)
    pete = next(i for i in r.impacts if i.user_id == 12)
    assert any("becomes an internal user" in x for x in pete.lines)
    assert any("Pete" in line for line in r.card_lines())


@V
def test_company_restricted_user_loses_login(v):
    f = Fake(v)
    r = sim(f, W("res.users", [14], company_ids=[(6, 0, [1])]))
    dana = next(i for i in r.impacts if i.user_id == 14)
    assert "can no longer sign in" in dana.lines
    r = sim(f, W("res.company", [2], active=False))
    assert "can no longer sign in" in next(i for i in r.impacts if i.user_id == 14).lines


@V
def test_bot_demoted_mid_run_refused(v):
    f = Fake(v)
    f.users[15] = dict(name="Eve", login="eve", groups={2}, share=False, c=[1], cid=1)
    assert refused(sim(f, W("res.users", [BOT], **{_g(v): [(3, 2)]})), "Bot's own user")
    gu = "user_ids" if v >= 19 else "users"
    assert refused(sim(f, W("res.groups", [2], **{gu: [(3, BOT)]})), "Bot's own")
    assert refused(sim(f, W("res.groups", [2], implied_ids=[(3, 3)])), "Bot's own")
    assert refused(sim(f, lk.Change("res.users.apikeys", "unlink", (7,))), "Bot's own")
    f.acl.append(
        dict(
            id=3,
            model_id=[102, "ir.cron"],
            group_id=[2, "x"],
            active=True,
            perm_read=True,
            perm_write=True,
            perm_create=False,
            perm_unlink=False,
        )
    )
    acl = "ir.access" if v >= 20 else "ir.model.access"
    assert refused(sim(f, W(acl, [3], active=False)), "apply to the Bot")


def test_group_field_names_per_major():
    assert refused(sim(Fake(17), W("res.users", [11], group_ids=[(4, 2)])), "on this Odoo")
    assert refused(sim(Fake(20), W("res.users", [11], groups_id=[(4, 2)])), "on this Odoo")
    assert refused(sim(Fake(17), W("res.users", [2], in_group_2=False)), "no working admin")
    assert refused(sim(Fake(17), W("res.users", [2], sel_groups_2_3=3)), "no working admin")


def test_odoo20_effective_groups_cross_check():
    f = Fake(20)
    f.all_override[11] = [6]  # Odoo says Alice has fewer groups than our closure
    assert refused(sim(f, W("res.users", [12], lang="fr_FR")), "disagree")


# ---------------------------------------------------------------- impacts
@V
def test_acl_and_rule_and_menu_losses_listed(v):
    f = Fake(v)
    acl = (
        W("ir.access", [1], operation="rc")
        if v >= 20
        else W("ir.model.access", [1], perm_write=False)
    )
    r = sim(f, acl)
    who = {i.user_id: i.lines for i in r.impacts}
    # 20: the domain row 9 still grants edit, so only the record-visibility note remains
    want = "record rule changed" if v >= 20 else "can no longer edit model #100"
    assert set(who) == {11, 14} and any(want in x for x in who[11])
    r = sim(f, W("ir.access", [9], domain="[]") if v >= 20 else W("ir.rule", [1], active=False))
    assert {i.user_id for i in r.impacts} == {11, 14}
    assert any("domains are not evaluated" in x for x in r.reasons)
    r = sim(f, W("ir.ui.menu", [500], **{_g(v): [(6, 0, [6])]}))
    assert {i.user_id for i in r.impacts} == {14}  # Alice (manager) keeps it
    assert r.counts["users_affected"] == 1


@V
def test_blanket_auth_paths_escalate(v):
    f = Fake(v)
    r = sim(f, W("ir.mail_server", [1], active=False))
    assert isinstance(r, lk.LockoutSim) and any("password-reset" in x for x in r.reasons)
    r = sim(f, W("ir.config_parameter", [1], value="False"))
    assert any("login/signup/reset" in x for x in r.reasons)
    f.oauth[2] = 9
    assert refused(sim(f, W("auth.oauth.provider", [9], enabled=False)), "no working admin")


# ---------------------------------------------------------------- fail closed
@V
def test_fail_closed(v):
    f = Fake(v)
    assert refused(sim(f, lk.Change("res.users", "unlink", (11,))), "archive")
    assert refused(sim(f, lk.Change("res.groups", "unlink", (5,))), "remove members")
    assert refused(sim(f, W("res.users", [11], **{_g(v): [(0, 0, {"name": "x"})]})), "command")
    assert refused(sim(f, W("res.users", [99], active=False)), "unreadable")
    assert refused(sim(f, W("res.users", [11], api_key_ids=[(5,)])), "unknown")
    assert refused(sim(f, lk.Change("res.users.deletion", "create", ())), "not simulated")
    assert refused(sim(f), "empty")
    assert refused(sim(f, W("res.users", [11], active=False), bot=0), "bot user")
    f.fail.add("ir.access" if v >= 20 else "ir.rule")
    assert refused(sim(f, W("res.users", [11], active=False)), "unreadable")
    assert all(m in ("fields_get", "search_read", "read") for _, m in f.calls)


@V
def test_password_change_is_not_revertible(v):
    r = sim(Fake(v), W("res.users", [11], password="new"))
    assert isinstance(r, lk.LockoutSim) and r.revertible is False
    assert any("not revertible" in x for x in r.reasons)
    assert any("sign-in details change" in x for i in r.impacts for x in i.lines)


def test_readonly_wrapper_blocks_writes():
    with pytest.raises(PermissionError):
        lk.df.ReadOnly(Fake())("res.users", "write", [[2], {}])


# ---------------------------------------------------------------- guard: weaker live job
def test_open_job_refuses_weaker_live_job(gate):  # noqa: F811
    sw = gate.switch
    gid = sw.create_grant(OWNER, "fp", "q" * 64, 1, 1, "alice", "bot-1", rehearsal_id="rh-a")
    got = sw.open_job("fp", "q" * 64, 1, 1, gid, gd.Approval(1, "alice", gid), "bot-1", "rh-a")
    assert not isinstance(got, Refusal)
    again = sw.open_job("fp", "q" * 64, 1, 3, None, gd.Approval(3, "alice", None), "bot-1", "rh-a")
    assert isinstance(again, Refusal) and "live job is L1 < L3" in again.reason
    same = sw.open_job("fp", "q" * 64, 1, 1, None, gd.Approval(1, "alice", None), "bot-1", "rh-a")
    assert not isinstance(same, Refusal) and same[2] is True


# ---------------------------------------------------------------- review round 1 (permanent)
def test_role_field_refused_on_20_and_absent_on_17():
    assert refused(sim(Fake(20), W("res.users", [2], role="group_user")), "allowlist")
    assert refused(sim(Fake(20), W("res.users", [11], role="group_system")), "allowlist")
    assert refused(sim(Fake(17), W("res.users", [2], role="group_user")), "unknown")
    assert refused(sim(Fake(20), W("res.users", [2], auth_method="passkey")), "unknown")


def test_allowlist_is_reviewed_and_disjoint():
    for model, allow in lk.FIELD_ALLOWLIST.items():
        assert not set(allow) & lk.HANDLED_FIELDS.get(model, frozenset())
        assert all(len(why) > 4 for why in allow.values())
        assert not set(allow) & rules.SECURITY_FIELDS
        assert not any(rules.credential_match(model, f) for f in allow)
    meta = {"lang": {"type": "selection", "store": False}}
    assert "computed" in lk.field_verdict("res.users", "lang", meta)
    rel = {"name": {"type": "many2one", "relation": "res.groups"}}
    assert "security model" in lk.field_verdict("res.users", "name", rel)


@V
def test_every_prefix_is_checked(v):
    gu = "user_ids" if v >= 19 else "users"
    f = Fake(v)
    f.users[15] = dict(name="Eve", login="eve", groups={2}, share=False, c=[1], cid=1)
    r = sim(f, W("res.users", [2], **{_g(v): [(3, 2)]}), W("res.users", [15], active=False))
    assert refused(r, "step 2: would leave no working admin")
    r = sim(
        f,
        W("res.users", [15], active=False),
        W("res.users", [15], active=True),
        W("res.users", [2], **{_g(v): [(3, 2)]}),
    )
    assert isinstance(r, lk.LockoutSim)
    r = sim(f, W("res.users", [2, 15], active=False), W("res.users", [2, 15], active=True))
    assert refused(r, "step 1: would leave no working admin")
    r = sim(
        f, W("res.groups", [2], **{gu: [(5,)]}), W("res.groups", [2], **{gu: [(6, 0, [2, BOT])]})
    )
    assert refused(r, "step 1")
    r = sim(f, W("res.groups", [2], **{gu: [(3, BOT)]}), W("res.groups", [2], **{gu: [(4, BOT)]}))
    assert refused(r, "step 1: changes the Bot's own group membership")
    r = sim(f, W("res.groups", [5], **{gu: [(4, BOT)]}))  # even a grant to the Bot is refused
    assert refused(r, "Bot's own group membership")


@V
def test_new_cycle_refused_even_when_one_exists(v):
    f = Fake(v)
    f.groups[1] = ("Internal User", [5])  # existing cycle 1 -> 5 -> 1
    r = sim(f, W("res.users", [11], lang="fr_FR"))
    assert isinstance(r, lk.LockoutSim) and any("already exist" in x for x in r.reasons)
    r = sim(f, W("res.groups", [3], implied_ids=[(4, 2)]))  # new cycle 2 -> 3 -> 2
    assert refused(r, "circular") and "[2, 3]" in r.reason
    f.groups[7] = ("Orphan A", [8])  # cycle among groups nobody holds still counts
    f.groups[8] = ("Orphan B", [])
    assert refused(sim(f, W("res.groups", [8], implied_ids=[(4, 7)])), "circular")


@V
def test_created_ids_are_unique(v):
    mk = lk.Change("res.users", "create", (), {"name": "N1", "login": "n1"})
    mk2 = lk.Change("res.users", "create", (), {"name": "N2", "login": "n2"})
    gr = lk.Change("res.groups", "create", (), {"name": "G"})
    r = sim(Fake(v), mk, mk2, gr, gr)
    assert isinstance(r, lk.LockoutSim)
    st = lk.State({}, {}, {}, {}, [], [])
    assert [st.new_id(), st.new_id(), st.new_id()] == [-1, -2, -3]


def test_created_ir_access_shows_permission_gains():
    r = sim(
        Fake(20),
        lk.Change(
            "ir.access",
            "create",
            (),
            {"model_id": 103, "group_id": 5, "operation": "rc", "name": "x"},
        ),
    )
    who = {i.user_id: i.lines for i in r.impacts}
    assert any("can now create/open model #103" in x for x in who[11])
    assert refused(
        sim(Fake(20), lk.Change("ir.access", "create", (), {"model_id": 103, "operation": "r"})),
        "Bot",
    )  # global row applies to the Bot

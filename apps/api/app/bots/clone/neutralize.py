"""Neutralize a rehearsal target over RPC and prove it by per-field read-back.

The rule set is structural: ``OUTBOUND`` covers every model the risk classifier floors as
sensitive (``rules.SENSITIVE_MODELS``) or that carries an outbound stem (``OUTBOUND_STEMS``:
environment / mode / webhook / endpoint / smtp / refresh-token / secret / api-key ...) in
``fields_inventory.csv`` for 17-20; each such model is either neutralized here or listed in
``NOT_OUTBOUND`` with a reviewed reason (drift test: tests/test_nf_bot_clone.py). Every rule
writes the target, then reads EVERY record of the field back; a write that errors, is silently
ignored, or reads back wrong refuses the rehearsal (fail closed). A model or field that is not
installed is "n/a". Specials: one loopback SMTP trap (so Odoo never falls back to odoo.conf),
no mail.template pinned to another server, database.is_neutralized read back.
Route B also runs Odoo's own ``odoo neutralize`` first (rehearse.Cloner).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.bots.clone.fingerprint import Rpc, get_param, set_param

TRAP_HOST, TRAP_PORT, TRAP_NAME = "127.0.0.1", 9, "ingenium rehearsal smtp trap"
TRAP_URL = f"http://{TRAP_HOST}:{TRAP_PORT}/ingenium-rehearsal-disabled"
DISABLED_TOKEN = "ingenium_rehearsal+disabled"
UNLINK = object()  # rule value: remove every record (push subscriptions)
OUTBOUND_STEMS = (
    "environment",
    "edi_mode",
    "webhook",
    "endpoint",
    "smtp_",
    "refresh_token",
    "rtoken",
    "sync_token",
    "client_secret",
    "api_key",
    "ldap_",
    "account_token",
    "password",
    "passwd",
    "_pass",
)


@dataclass(frozen=True)
class Rule:
    key: str
    model: str
    field: str
    value: Any
    ok: Callable[[Any], bool]


def _is(*vals: Any) -> Callable[[Any], bool]:
    return lambda v: v in vals


_FALSY = _is(False, None, "")
RULES: tuple[Rule, ...] = (
    Rule("cron", "ir.cron", "active", False, _is(False)),
    Rule("automation", "base.automation", "active", False, _is(False)),
    Rule(
        "server_webhook",
        "ir.actions.server",
        "webhook_url",
        TRAP_URL,
        _is(False, None, "", TRAP_URL),
    ),
    Rule("fetchmail", "fetchmail.server", "active", False, _is(False)),
    Rule(
        "iap",
        "iap.account",
        "account_token",
        DISABLED_TOKEN,
        lambda v: str(v or "").endswith("+disabled"),
    ),
    Rule("payment", "payment.provider", "state", "disabled", _is("disabled", "test")),
    Rule("payment_token", "payment.token", "active", False, _is(False)),
    Rule("delivery_env", "delivery.carrier", "prod_environment", False, _is(False)),
    Rule("edi_proxy", "account_edi_proxy_client.user", "edi_mode", "demo", _is("demo")),
    Rule("pos_terminal", "pos.payment.method", "use_payment_terminal", False, _FALSY),
    Rule("oauth", "auth.oauth.provider", "enabled", False, _is(False)),
    Rule("ldap", "res.company.ldap", "ldap_server", TRAP_HOST, _is(TRAP_HOST)),
    Rule("gcal_cred", "google.calendar.credentials", "calendar_rtoken", False, _FALSY),
    Rule("gcal_user", "res.users.settings", "google_calendar_rtoken", False, _FALSY),
    Rule("mscal_user", "res.users", "microsoft_calendar_rtoken", False, _FALSY),
    Rule("calendar_user", "calendar.user", "google_sync_token", False, _FALSY),
    Rule("push_device", "mail.push.device", "id", UNLINK, lambda v: False),
    Rule("push_partner_device", "mail.partner.device", "id", UNLINK, lambda v: False),
)
# Reviewed: in scope of the drift test but cannot send anything from the copy on their own.
NOT_OUTBOUND: dict[str, str] = {
    "ir.mail_server": "special: every server off except the loopback trap (read back)",
    "res.partner.bank": "bank master data; no sender",
    "res.bank": "bank master data; no sender",
    "website.rewrite": "inbound URL redirects",
    "auth.passkey.key": "inbound login credential",
    "res.users.identitycheck": "transient inbound password check",
    "change.password.own": "transient inbound password wizard",
    "change.password.user": "transient inbound password wizard",
    "res.config.settings": "transient settings wizard; stored values are ir.config_parameter",
    "calendar.provider.config": "transient calendar setup wizard",
    "iap.account.info": "transient IAP info view; token lives on iap.account (neutralized)",
    "google.gmail.mixin": "abstract mixin; ir.mail_server/fetchmail.server are off",
    "microsoft.outlook.mixin": "abstract mixin; ir.mail_server/fetchmail.server are off",
    "microsoft.calendar.credentials": "sync token only; refresh token res.users is cleared",
    "res.partner": "peppol/routing endpoint is the partner's address; sender is edi proxy user",
    "res.groups": "api_key_duration is inbound API key policy",
    "ir.ui.view": "visibility_password guards an inbound page",
    "purchase.report": "delay_pass is a report measure",
    "website": "browser-side map/places keys; no server-initiated send",
    "sms.sms": "SMS go through IAP; iap.account token disabled",
}


class NeutralizeError(Exception):
    def __init__(self, failed: dict[str, str]) -> None:
        super().__init__("not neutralized: " + ", ".join(f"{k}={v}" for k, v in failed.items()))
        self.failed = failed


_CTX = {"context": {"active_test": False}}


def _has(rpc: Rpc, model: str) -> bool:
    return bool(rpc("ir.model", "search_count", [[("model", "=", model)]], None))


def _has_field(rpc: Rpc, r: Rule) -> bool:
    if not _has(rpc, r.model):
        return False
    return r.value is UNLINK or r.field in (
        rpc(r.model, "fields_get", [], {"attributes": ["type"]}) or {}
    )


def _ids(rpc: Rpc, model: str, dom: list) -> list[int]:
    return list(rpc(model, "search", [dom], _CTX) or [])


def _count(rpc: Rpc, model: str, dom: list) -> int:
    return int(rpc(model, "search_count", [dom], _CTX))


def _rows(rpc: Rpc, r: Rule) -> list[dict]:
    return list(rpc(r.model, "search_read", [[]], {**_CTX, "fields": [r.field]}) or [])


def _trap_ids(rpc: Rpc) -> list[int]:
    dom = [("smtp_host", "=", TRAP_HOST), ("smtp_port", "=", TRAP_PORT), ("name", "=", TRAP_NAME)]
    return _ids(rpc, "ir.mail_server", dom)


def _off(rpc: Rpc, model: str, dom: list, vals: dict) -> None:
    if ids := _ids(rpc, model, dom):
        rpc(model, "write", [ids, vals], None)


def _apply(rpc: Rpc, r: Rule) -> None:
    if not _has_field(rpc, r):
        return
    if r.value is UNLINK:
        if ids := _ids(rpc, r.model, []):
            rpc(r.model, "unlink", [ids], None)
        return
    if bad := [x["id"] for x in _rows(rpc, r) if not r.ok(x.get(r.field))]:
        rpc(r.model, "write", [bad, {r.field: r.value}], None)


def neutralize(rpc: Rpc) -> None:
    """Writes to the TARGET only; the caller has already proved the target is not prod.
    Every rule is attempted even when an earlier one fails; the read-back decides."""
    errors: list[BaseException] = []

    def step(fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - reported by the read-back
            errors.append(exc)

    step(lambda: _mail(rpc))
    for r in RULES:
        step(lambda r=r: _apply(rpc, r))
    step(lambda: set_param(rpc, "database.is_neutralized", "true"))  # Odoo's own value
    if errors:
        raise errors[0]


def _mail(rpc: Rpc) -> None:
    trap = _trap_ids(rpc)
    _off(rpc, "ir.mail_server", [("active", "=", True), ("id", "not in", trap)], {"active": False})
    if not trap:
        vals = {
            "name": TRAP_NAME,
            "smtp_host": TRAP_HOST,
            "smtp_port": TRAP_PORT,
            "smtp_encryption": "none",
            "sequence": 0,
            "active": True,
        }
        trap = [rpc("ir.mail_server", "create", [vals], None)]
    rpc("ir.mail_server", "write", [trap, {"active": True, "sequence": 0}], None)
    if _has(rpc, "mail.template"):
        dom = [("mail_server_id", "!=", False), ("mail_server_id", "not in", trap)]
        _off(rpc, "mail.template", dom, {"mail_server_id": False})


def _readback(rpc: Rpc, r: Rule) -> str:
    if not _has_field(rpc, r):
        return "n/a"
    if r.value is UNLINK:
        return "ok" if _count(rpc, r.model, []) == 0 else "FAIL"
    rows = _rows(rpc, r)
    return "ok" if all(r.ok(x.get(r.field)) for x in rows) else "FAIL"


def _special(rpc: Rpc) -> dict[str, Callable[[], str]]:
    def b(v: bool) -> str:
        return "ok" if v is True else "FAIL"

    def trap_ok() -> str:
        t = _trap_ids(rpc)
        dom = [("id", "in", t), ("active", "=", True)]
        return b(len(t) == 1 and _count(rpc, "ir.mail_server", dom) == 1)

    def servers_ok() -> str:
        dom = [("active", "=", True), ("id", "not in", _trap_ids(rpc))]
        return b(_count(rpc, "ir.mail_server", dom) == 0)

    def tmpl_ok() -> str:
        if not _has(rpc, "mail.template"):
            return "n/a"
        dom = [("mail_server_id", "!=", False), ("mail_server_id", "not in", _trap_ids(rpc))]
        return b(_count(rpc, "mail.template", dom) == 0)

    return {
        "mail_server": servers_ok,
        "smtp_trap": trap_ok,
        "mail_template": tmpl_ok,
        "neutralized_flag": lambda: b(
            (get_param(rpc, "database.is_neutralized") or "").lower() == "true"
        ),
    }


ITEMS = ("mail_server", "smtp_trap", "mail_template", *(r.key for r in RULES), "neutralized_flag")


def check(rpc: Rpc) -> dict[str, str]:
    """item -> 'ok' | 'n/a' | 'FAIL...'. Any exception is a FAIL (fail-closed)."""
    fns: dict[str, Callable[[], str]] = _special(rpc)
    fns.update({r.key: (lambda r=r: _readback(rpc, r)) for r in RULES})
    out: dict[str, str] = {}
    for item in ITEMS:
        try:
            out[item] = fns[item]()
        except Exception as exc:  # noqa: BLE001 - unreadable = not neutralized
            out[item] = f"FAIL:{type(exc).__name__}"
    return out


def assert_neutralized(rpc: Rpc) -> dict[str, str]:
    res = check(rpc)
    failed = {k: v for k, v in res.items() if v not in ("ok", "n/a")}
    if failed or set(res) != set(ITEMS):
        raise NeutralizeError(failed or {"items": "incomplete"})
    return res


def neutralize_and_check(rpc: Rpc) -> dict[str, str]:
    try:
        neutralize(rpc)
    except Exception as exc:  # noqa: BLE001 - a failed write is reported by the read-back
        res: Any = check(rpc)
        res["write"] = f"FAIL:{type(exc).__name__}"
        raise NeutralizeError({k: v for k, v in res.items() if v not in ("ok", "n/a")}) from exc
    return assert_neutralized(rpc)

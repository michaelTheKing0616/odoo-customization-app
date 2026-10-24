"""NF BV-LIVE: disposable ingenium_nf_bv_{17..20} databases on the isolated sandbox stacks.

Stacks come from ``app.sandbox.sandbox_stack_for_major`` (ports 18117-18120,
never 8069-8073). Each database is created for the run, seeded with personas
and PII strings, and dropped afterwards; the drop is asserted. Passwords are
random per run (or INGENIUM_NF_BV_MASTER_PW) and are never logged or printed.
"""

from __future__ import annotations

import os
import re
import secrets
import subprocess
import tempfile
import time
import urllib.request
import xmlrpc.client
from dataclasses import dataclass, field
from typing import Any

from app.bot_verify.readback import PortUnavailable
from app.sandbox import DEV_PORTS, REPO_ROOT, SANDBOX_COMPOSE, sandbox_stack_for_major

VERSIONS: tuple[int, ...] = (17, 18, 19, 20)
_DB_RX = re.compile(r"^ingenium_nf_bv_(17|18|19|20)$")
MODULES = "base,crm,base_automation"
PII_STRINGS: tuple[str, ...] = (
    "Zelda Quartermain",
    "zelda.q@nfbv.example",
    "Chief Pii Officer ZQX",
    "secret note ZQX-PII-7731",
)


class AccessError(Exception):
    """Odoo answered an access fault (XML-RPC fault code 3 or 4)."""


class SeedError(RuntimeError):
    """Live seed step failed; message never carries credentials."""


def db_name_for(major: int) -> str:
    name = f"ingenium_nf_bv_{int(major)}"
    guard_db(name)
    return name


def guard_db(name: str) -> None:
    if not _DB_RX.match(str(name)):
        raise SeedError("refused: only ingenium_nf_bv_{17..20} databases")


def _stack(major: int) -> Any:
    stack = sandbox_stack_for_major(major)
    if stack.port in DEV_PORTS or not 18117 <= stack.port <= 18120:
        raise SeedError(f"refused port {stack.port}")
    return stack


def _run(
    cmd: list[str], *, env: dict | None = None, timeout: float = 900
) -> subprocess.CompletedProcess:
    cp = subprocess.run(
        cmd, capture_output=True, text=True, env=env, timeout=timeout, cwd=str(REPO_ROOT)
    )
    if cp.returncode != 0:
        raise SeedError(f"{' '.join(cmd[:4])} failed rc={cp.returncode}")
    return cp


def _compose_env(major: int) -> dict[str, str]:
    stack = _stack(major)
    addons = os.path.join(tempfile.gettempdir(), "ingenium_nf_bv_addons")
    os.makedirs(addons, exist_ok=True)
    return {
        **os.environ,
        "ODOO_SANDBOX_IMAGE": f"odoo:{int(major)}",
        "ISB_NAME": stack.project,
        "ISB_PORT": str(stack.port),
        "ISB_ADDONS": addons,
    }


def _compose(major: int, *args: str) -> None:
    stack = _stack(major)
    _run(
        ["docker", "compose", "-p", stack.project, "-f", str(SANDBOX_COMPOSE), *args],
        env=_compose_env(major),
    )


def stack_running(major: int) -> bool:
    stack = _stack(major)
    cp = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", stack.odoo_container],
        capture_output=True,
        text=True,
    )
    return cp.returncode == 0 and cp.stdout.strip() == "true"


def stack_up(major: int) -> bool:
    """Start the sandbox stack when it is down. Returns True when this call started it."""
    if stack_running(major):
        return False
    _compose(major, "up", "-d")
    return True


def stack_down(major: int) -> None:
    _compose(major, "down", "-v", "--remove-orphans")


def wait_http(major: int, timeout_s: float = 240) -> None:
    url = f"{_stack(major).url}/web/webclient/version_info"
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            req = urllib.request.Request(
                url, data=b"{}", headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 - loopback sandbox only
                if resp.status == 200:
                    return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(3)
    raise SeedError(f"sandbox v{major} did not answer")


def _psql(major: int, sql: str) -> str:
    stack = _stack(major)
    cp = _run(
        ["docker", "exec", stack.db_container, "psql", "-U", "odoo", "-d", "postgres", "-tAc", sql]
    )
    return cp.stdout


def db_exists(major: int) -> bool:
    name = db_name_for(major)
    return _psql(major, f"SELECT 1 FROM pg_database WHERE datname = '{name}'").strip() == "1"


def drop_db(major: int) -> None:
    name = db_name_for(major)
    _psql(major, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def create_db(major: int) -> None:
    """No demo data; server CLI installs modules, then the worker restarts (registry reload)."""
    name = db_name_for(major)
    if db_exists(major):
        raise SeedError(f"{name} already exists; refusing to reuse it")
    # Worker stopped during init: a live worker touching a half-built DB caches a broken registry.
    _compose(major, "stop", "odoo")
    try:
        cmd = [
            "run",
            "--rm",
            "--no-deps",
            "odoo",
            "odoo",
            "--db_host=db",
            "-r",
            "odoo",
            "-w",
            "odoo",
        ]
        cmd += ["-d", name, "-i", MODULES, "--stop-after-init", "--no-http", "--log-level=warn"]
        if major < 19:
            cmd.append("--without-demo=all")
        _compose(major, *cmd)
    finally:
        _compose(major, "start", "odoo")
    wait_http(major)


@dataclass
class LivePort:
    """Read port for the collector plus an admin write channel for seeding/applying."""

    major: int
    url: str
    db_name: str
    admin_uid: int = 0
    _pw: dict[int, str] = field(default_factory=dict, repr=False)
    personas: dict[str, int] = field(default_factory=dict)
    uids_seen: set[int] = field(default_factory=set)

    def _proxy(self) -> xmlrpc.client.ServerProxy:
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)

    def _exec(self, uid: int, model: str, method: str, args: Any, kwargs: dict) -> Any:
        self.uids_seen.add(uid)
        try:
            return self._proxy().execute_kw(
                self.db_name, uid, self._pw[uid], model, method, list(args), kwargs
            )
        except xmlrpc.client.Fault as exc:
            if exc.faultCode in (3, 4):
                raise AccessError("access denied") from None
            raise
        except xmlrpc.client.ProtocolError as exc:
            if exc.errcode in (429, 503):
                raise PortUnavailable(exc.errcode, (exc.headers or {}).get("Retry-After")) from None
            raise

    def call(
        self,
        model: str,
        method: str,
        args: Any = (),
        kwargs: dict | None = None,
        *,
        as_uid: int | None = None,
    ) -> Any:
        return self._exec(
            as_uid if isinstance(as_uid, int) else self.admin_uid, model, method, args, kwargs or {}
        )

    def admin(self, model: str, method: str, args: Any = (), kwargs: dict | None = None) -> Any:
        return self._exec(self.admin_uid, model, method, args, kwargs or {})

    def login(self, login: str, password: str) -> int:
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(self.db_name, login, password, {})
        if not isinstance(uid, int) or not uid:
            raise SeedError(f"login failed for persona {login}")
        self._pw[uid] = password
        return uid

    def xmlid(self, module: str, name: str) -> int:
        rows = self.admin(
            "ir.model.data",
            "search_read",
            ([("module", "=", module), ("name", "=", name)],),
            {"fields": ["res_id"], "limit": 1},
        )
        if not rows:
            raise SeedError(f"xmlid {module}.{name} missing")
        return int(rows[0]["res_id"])

    @property
    def groups_key(self) -> str:
        return "groups_id" if self.major < 19 else "group_ids"


PERSONA_GROUPS: dict[str, tuple[str, str]] = {
    "requester": ("sales_team", "group_sale_manager"),
    "low_privilege": ("base", "group_user"),
    "portal": ("base", "group_portal"),
}


def seed(major: int) -> LivePort:
    """Admin password rotated to a random secret, three persona users, one PII partner."""
    stack = _stack(major)
    port = LivePort(major=major, url=stack.url, db_name=db_name_for(major))
    port.admin_uid = port.login("admin", "admin")
    admin_pw = os.environ.get("INGENIUM_NF_BV_MASTER_PW") or secrets.token_urlsafe(24)
    port.admin("res.users", "write", ([port.admin_uid], {"password": admin_pw}))
    port.admin_uid = port.login("admin", admin_pw)
    for persona, (module, xml) in PERSONA_GROUPS.items():
        gid = port.xmlid(module, xml)
        pw = secrets.token_urlsafe(18)
        login = f"nf_bv_{persona}"
        port.admin(
            "res.users",
            "create",
            (
                {
                    "name": f"NF BV {persona}",
                    "login": login,
                    "password": pw,
                    port.groups_key: [(6, 0, [gid])],
                },
            ),
        )
        port.personas[persona] = port.login(login, pw)
    port.admin(
        "res.partner",
        "create",
        (
            {
                "name": PII_STRINGS[0],
                "email": PII_STRINGS[1],
                "function": PII_STRINGS[2],
                "comment": PII_STRINGS[3],
                "ref": "NFBV-PII",
            },
        ),
    )
    return port

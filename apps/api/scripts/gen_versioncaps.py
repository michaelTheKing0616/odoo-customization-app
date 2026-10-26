"""Generate the Odoo version-capability catalogue (app/bots/versioncaps/data/caps_<v>.json.gz).

Clean-room: only the public ORM over XML-RPC is used; no Odoo source file is read.
Per version: start a disposable sandbox (docker/docker-compose.ingenium-sandbox.yml), init a
throwaway DB, install every installable Community module (skipping l10n_*/theme_*/test_*/hw_*),
bisecting batches so one failing or conflicting module never blocks the rest (recorded as
``not_introspectable``), then read ir.module.module, ir.model, ir.model.fields and
ir.model.fields.selection. Output is sorted, compact, gzip (mtime 0) -> deterministic.

    python scripts/gen_versioncaps.py 17 20 [--port-base 18300] [--keep]
"""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
import time
import xmlrpc.client
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "docker" / "docker-compose.ingenium-sandbox.yml"
OUT = Path(__file__).resolve().parents[1] / "app" / "bots" / "versioncaps" / "data"
DB = "caps"
SKIP_PREFIX = ("l10n_", "theme_", "test_", "hw_")
KEEP_L10N = {"l10n_generic_coa"}


def sh(*a: str, env: dict | None = None, check: bool = True) -> str:
    import os

    r = subprocess.run(a, capture_output=True, text=True, env={**os.environ, **(env or {})})
    if check and r.returncode:
        raise RuntimeError(f"{a[:4]}: {r.stderr[-800:]}")
    return r.stdout


class Box:
    def __init__(self, v: int, port: int) -> None:
        self.v, self.port, self.name = v, port, f"ingenium_caps_v{v}"
        self.addons = tempfile.mkdtemp(prefix="caps_addons_")
        self.env = {
            "ISB_NAME": self.name,
            "ISB_PORT": str(port),
            "ISB_ADDONS": self.addons,
            "ODOO_SANDBOX_IMAGE": f"odoo:{v}",
        }

    def compose(self, *a: str) -> str:
        return sh("docker", "compose", "-p", self.name, "-f", str(COMPOSE), *a, env=self.env)

    def up(self) -> None:
        self.compose("up", "-d", "--wait")
        demo = ["--without-demo=all"] if self.v < 19 else []
        sh(
            "docker",
            "exec",
            f"{self.name}_odoo",
            "odoo",
            "--db_host=db",
            "--db_user=odoo",
            "--db_password=odoo",
            "-d",
            DB,
            "-i",
            "base",
            *demo,
            "--stop-after-init",
        )
        sh("docker", "restart", f"{self.name}_odoo")  # drop any registry cached before init
        self.wait()

    def wait(self) -> None:
        url = f"http://127.0.0.1:{self.port}"
        for _ in range(60):
            try:
                if xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(
                    DB, "admin", "admin", {}
                ):
                    break
            except Exception:  # noqa: BLE001 - server still starting
                pass
            time.sleep(2)
        self.uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(
            DB, "admin", "admin", {}
        )
        self.obj = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)

    def down(self) -> None:
        self.compose("down", "-v")

    def call(self, model: str, method: str, *a, **kw):
        return self.obj.execute_kw(DB, self.uid, "admin", model, method, list(a), kw)


def install_all(b: Box, log=print) -> list[str]:
    """Install via the Odoo CLI in batches (robust to long installs); success = module state."""
    b.call("ir.module.module", "update_list")
    mods = b.call(
        "ir.module.module", "search_read", [["state", "=", "uninstalled"]], fields=["name"]
    )
    want = sorted(
        m["name"] for m in mods if not m["name"].startswith(SKIP_PREFIX) or m["name"] in KEEP_L10N
    )
    failed: list[str] = []
    odoo = f"{b.name}_odoo"
    sh("docker", "stop", odoo)  # one writer: the CLI

    def pending(names: list[str]) -> list[str]:
        names_sql = ",".join(f"'{n}'" for n in names)  # module names from Odoo's own list
        q = f"select name from ir_module_module where state<>'installed' and name in ({names_sql})"
        out = sh("docker", "exec", f"{b.name}_db", "psql", "-U", "odoo", "-d", DB, "-Atc", q)
        return sorted(out.split())

    def attempt(names: list[str]) -> None:
        names = pending(names)
        if not names:
            return
        sh(
            "docker",
            "run",
            "--rm",
            "--network",
            f"{b.name}_default",
            "-v",
            f"{b.name}_sandbox-web-data:/var/lib/odoo",
            f"odoo:{b.v}",
            "odoo",
            "--db_host=db",
            "--db_user=odoo",
            "--db_password=odoo",
            "-d",
            DB,
            "-i",
            ",".join(names),
            "--stop-after-init",
            check=False,
        )
        left = pending(names)
        log(f"  batch {len(names)} -> {len(names) - len(left)} ok")
        if not left:
            return
        if len(names) == 1:
            failed.append(names[0])
            log(f"  fail {names[0]}")
            return
        if len(left) < len(names):  # progress: retry only what is left
            attempt(left)
            return
        h = len(left) // 2
        attempt(left[:h])
        attempt(left[h:])

    for i in range(0, len(want), 80):
        attempt(want[i : i + 80])
    sh("docker", "start", odoo)
    b.wait()
    return sorted(failed)


MIN_DEPENDS_FRACTION = 0.8


def read_depends(b: Box) -> dict[str, list[str]]:
    """Technical module name -> sorted technical dependency names (module_id is an id)."""
    ids = {
        m["id"]: m["name"] for m in b.call("ir.module.module", "search_read", [], fields=["name"])
    }
    out: dict[str, set[str]] = {}
    for d in b.call("ir.module.module.dependency", "search_read", [], fields=["module_id", "name"]):
        n = ids.get(d["module_id"][0]) if d["module_id"] else None
        if n and d["name"]:
            out.setdefault(n, set()).add(d["name"])
    return {k: sorted(v) for k, v in sorted(out.items())}


def check_depends(mods: dict) -> None:
    """Fail loudly: nearly every module except base declares depends."""
    have = sum(1 for m in mods.values() if m["depends"])
    if not mods or have < MIN_DEPENDS_FRACTION * (len(mods) - 1):
        raise RuntimeError(f"only {have}/{len(mods)} modules have depends; dependency read broken")
    if "stock" not in mods.get("mrp", {}).get("depends", []):
        raise RuntimeError("mrp does not depend on stock; dependency read broken")


def refresh_depends(b: Box) -> Path:
    """Light path: depends come from the apps list alone (no installs). Same values a full run
    writes, because dependency rows are read from manifests at update_list time."""
    b.call("ir.module.module", "update_list")
    p = OUT / f"caps_{b.v}.json.gz"
    caps = json.loads(gzip.decompress(p.read_bytes()))
    deps = read_depends(b)
    for n, m in caps["modules"].items():
        m["depends"] = deps.get(n, [])
    check_depends(caps["modules"])
    return write(caps)


def read_caps(b: Box, failed: list[str]) -> dict:
    mods = {}
    for m in b.call(
        "ir.module.module",
        "search_read",
        [],
        fields=["name", "state", "application", "category_id", "auto_install", "license"],
    ):
        mods[m["name"]] = {
            "category": m["category_id"][1] if m["category_id"] else "",
            "application": bool(m["application"]),
            "auto_install": bool(m["auto_install"]),
            "state": m["state"],
            "depends": [],
        }
    for n, deps in read_depends(b).items():
        if n in mods:
            mods[n]["depends"] = deps
    check_depends(mods)
    models = {}
    for m in b.call("ir.model", "search_read", [], fields=["model", "modules", "transient"]):
        models[m["model"]] = {
            "modules": sorted(x.strip() for x in (m["modules"] or "").split(",") if x.strip()),
            "transient": bool(m["transient"]),
            "fields": {},
        }
    sel: dict[int, list[str]] = {}
    for s in b.call("ir.model.fields.selection", "search_read", [], fields=["field_id", "value"]):
        sel.setdefault(s["field_id"][0], []).append(s["value"])
    for f in b.call(
        "ir.model.fields",
        "search_read",
        [],
        fields=["model", "name", "ttype", "relation", "required", "modules"],
    ):
        if f["model"] not in models:
            continue
        mm = sorted(x.strip() for x in (f["modules"] or "").split(",") if x.strip())
        row = [f["ttype"], f["relation"] or "", bool(f["required"]), mm]
        if f["id"] in sel:
            row.append(sorted(sel[f["id"]]))
        models[f["model"]]["fields"][f["name"]] = row
    for m in models.values():
        m["fields"] = dict(sorted(m["fields"].items()))
    base = {
        k: v
        for k, v in b.call(
            "ir.module.module", "search_read", [["name", "=", "base"]], fields=["latest_version"]
        )[0].items()
        if k != "id"
    }
    return {
        "major": b.v,
        "edition": "community",
        "base_version": base.get("latest_version"),
        "skipped_prefixes": list(SKIP_PREFIX),
        "not_introspectable": failed,
        "field_row": ["type", "relation", "required", "modules", "selection?"],
        "modules": dict(sorted(mods.items())),
        "models": dict(sorted(models.items())),
    }


def write(caps: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"caps_{caps['major']}.json.gz"
    raw = json.dumps(caps, sort_keys=True, separators=(",", ":")).encode()
    with open(p, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
        gz.write(raw)
    return p


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("versions", nargs="+", type=int)
    ap.add_argument("--port-base", type=int, default=18300)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--depends-only", action="store_true", help="refresh depends in existing files")
    a = ap.parse_args(argv)
    for v in a.versions:
        b = Box(v, a.port_base + v)
        try:
            b.up()
            if a.depends_only:
                print(f"[{v}] depends refreshed {refresh_depends(b)}", flush=True)
                continue
            failed = install_all(b, log=lambda s, v=v: print(f"[{v}]{s}", flush=True))
            p = write(read_caps(b, failed))
            print(f"[{v}] wrote {p} failed={failed}", flush=True)
        finally:
            if not a.keep:
                b.down()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

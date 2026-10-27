"""Live check of the shipped version catalogue against a disposable Odoo sandbox (ws-caps-v<N>).

Per version: start a throwaway sandbox from odoo:<N>, refresh the apps list, install a fixed
sample of stock modules over XML-RPC (throwaway DB only), then compare with the catalogue:
image id vs provenance, listed modules, and every live model's fields (name, type, relation).
Catalogue verdicts are also checked against the live installed set. The sandbox is always removed.

    ODOO_LIVE=1 python scripts/verify_versioncaps_live.py 17 18 19 20 --out DIR

Exit 0 only when every version matches.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.bots import versioncaps as vc  # noqa: E402
from app.bots.versioncaps import caps as C  # noqa: E402

SAMPLE = ["sale_management", "purchase", "stock", "mrp", "account", "hr", "project"]
NOT_SAMPLED = "repair"  # a stock module left uninstalled: must say available-needs-install


def _gen():
    spec = importlib.util.spec_from_file_location("gen_vc", HERE / "gen_versioncaps.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def compare(caps: C.Caps, live_mods: set[str], live_fields: dict, skip: tuple[str, ...]) -> dict:
    """Pure: diff a live read against one catalogue. Empty lists mean a match."""
    keep = {m for m in live_mods if not m.startswith(skip)}
    listed = {m for m in caps.listed if not m.startswith(skip)}
    out: dict = {
        "modules_live_not_in_catalogue": sorted(keep - listed),
        "modules_catalogue_not_live": sorted(listed - keep),
        "models_live_not_in_catalogue": [],
        "fields_live_not_in_catalogue": [],
        "fields_type_mismatch": [],
    }
    for model, fields in sorted(live_fields.items()):
        cm = caps.models.get(model)
        if cm is None:
            out["models_live_not_in_catalogue"].append(model)
            continue
        for name, (ttype, rel) in sorted(fields.items()):
            row = cm["fields"].get(name)
            if row is None:
                out["fields_live_not_in_catalogue"].append(f"{model}.{name}")
            elif (row[0], row[1]) != (ttype, rel):
                out["fields_type_mismatch"].append(f"{model}.{name}")
    return out


def run(v: int, port_base: int) -> dict:
    g = _gen()
    caps = C.load(v)
    if caps is None:
        return {"version": v, "ok": False, "error": "no trusted catalogue"}
    b = g.Box(v, port_base + v)
    try:
        b.up()
        b.call("ir.module.module", "update_list")
        ids = b.call("ir.module.module", "search", [["name", "in", SAMPLE]])
        b.call("ir.module.module", "button_immediate_install", ids)
        b.wait()
        mods = b.call("ir.module.module", "search_read", [], fields=["name", "state"])
        live_mods = {m["name"] for m in mods}
        installed = sorted(m["name"] for m in mods if m["state"] == "installed")
        live: dict = {}
        for f in b.call(
            "ir.model.fields", "search_read", [], fields=["model", "name", "ttype", "relation"]
        ):
            live.setdefault(f["model"], {})[f["name"]] = (f["ttype"], f["relation"] or "")
        diff = compare(caps, live_mods, live, tuple(caps.data.get("skipped_prefixes", ())))
        prov = vc.provenance(v) or {}
        verdicts = {
            "sample_installed_ok": vc.availability(v, "community", installed, "mrp.bom").status,
            "not_sampled": vc.availability(
                v, "community", installed, "repair.order", module_hint=NOT_SAMPLED
            ).status,
        }
        res = {
            "version": v,
            "image_matches_provenance": g.image_id(v) == prov.get("image_id"),
            "installed": len(installed),
            "live_models": len(live),
            "live_fields": sum(len(x) for x in live.values()),
            "verdicts": verdicts,
            **{k: (len(x), x[:20]) for k, x in diff.items()},
        }
        res["ok"] = (
            res["image_matches_provenance"]
            and all(not x for x in diff.values())
            and verdicts
            == {"sample_installed_ok": "installed-ok", "not_sampled": "available-needs-install"}
        )
        return res
    finally:
        b.down()


def main(argv: list[str]) -> int:
    if os.environ.get("ODOO_LIVE") != "1":
        print("needs ODOO_LIVE=1 (starts docker sandboxes)")
        return 2
    ap = argparse.ArgumentParser()
    ap.add_argument("versions", nargs="+", type=int)
    ap.add_argument("--port-base", type=int, default=18100)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    ok = True
    for v in a.versions:
        r = run(v, a.port_base)
        ok &= bool(r.get("ok"))
        print(json.dumps(r, sort_keys=True), flush=True)
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            (a.out / f"live_{v}.json").write_text(json.dumps(r, indent=1, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

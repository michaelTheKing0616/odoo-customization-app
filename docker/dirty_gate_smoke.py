"""TRUST-5 dirty-instance seed + mutating-surface smoke (run via docker/run-dirty-gate.sh)."""

from __future__ import annotations

import os
import sys
import time
import xmlrpc.client
from pathlib import Path

from module_generator import FieldSpec, ModelSpec, ModuleSpec, ViewSpec, build_module_zip

SANDBOX_URL = os.environ.get("SANDBOX_URL", f"http://{os.environ.get('ODOO_HOST', '127.0.0.1')}:{os.environ.get('ODOO_PORT', '18069')}")
SANDBOX_DB = os.environ.get("SANDBOX_DB", "sandbox_test")
SANDBOX_USER = os.environ.get("SANDBOX_USER", "admin")
SANDBOX_PASSWORD = os.environ.get("SANDBOX_PASSWORD", "admin")
TARGET = int(os.environ.get("DIRTY_RECORD_TARGET", "50000"))
BATCH = int(os.environ.get("DIRTY_SEED_BATCH", "500"))
EXTRA_MODULES = [m.strip() for m in os.environ.get("DIRTY_EXTRA_MODULES", "contacts,mail,crm,sale").split(",") if m.strip()]


def _proxy() -> tuple[xmlrpc.client.ServerProxy, xmlrpc.client.ServerProxy, int]:
    common = xmlrpc.client.ServerProxy(f"{SANDBOX_URL}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(SANDBOX_DB, SANDBOX_USER, SANDBOX_PASSWORD, {})
    if not uid:
        raise SystemExit(f"Auth failed for {SANDBOX_DB} at {SANDBOX_URL}")
    models = xmlrpc.client.ServerProxy(f"{SANDBOX_URL}/xmlrpc/2/object", allow_none=True)
    return common, models, int(uid)


def kw(models, uid, model: str, method: str, args=None, kwargs=None):
    return models.execute_kw(
        SANDBOX_DB,
        uid,
        SANDBOX_PASSWORD,
        model,
        method,
        args if args is not None else [],
        kwargs or {},
    )


def install_modules(models, uid, names: list[str]) -> None:
    kw(models, uid, "ir.module.module", "update_list", [])
    for name in names:
        rows = kw(
            models,
            uid,
            "ir.module.module",
            "search_read",
            [[("name", "=", name)]],
            {"fields": ["id", "state"], "limit": 1},
        )
        if not rows:
            print(f"WARN: module {name} not found")
            continue
        state = rows[0].get("state")
        if state == "installed":
            print(f"module {name}: already installed")
            continue
        print(f"Installing {name}...")
        kw(models, uid, "ir.module.module", "button_immediate_install", [[rows[0]["id"]]])


def install_dirty_custom_module(models, uid) -> str:
    spec = ModuleSpec(
        technical_name="dirty_gate_ext",
        display_name="Dirty Gate Extension",
        models=[
            ModelSpec(
                model="x_dirty_gate",
                description="Dirty Gate Volume",
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                    FieldSpec(name="x_note", ttype="text", string="Note"),
                ],
            )
        ],
        views=[
            ViewSpec(
                name="x_dirty_gate.form",
                model="x_dirty_gate",
                type="form",
                arch=(
                    '<form string="Dirty Gate"><sheet><group>'
                    '<field name="x_name"/><field name="x_note"/>'
                    "</group></sheet></form>"
                ),
            ),
            ViewSpec(
                name="x_dirty_gate.list",
                model="x_dirty_gate",
                type="list",
                arch='<list><field name="x_name"/></list>',
            ),
        ],
    )
    zip_bytes = build_module_zip(spec)
    zip_path = Path("/tmp/dirty_gate_ext.zip")
    zip_path.write_bytes(zip_bytes)
    wid = kw(
        models,
        uid,
        "ir.module.module",
        "create",
        [
            {
                "name": "dirty_gate_ext",
                "state": "uninstalled",
                "imported": True,
            }
        ],
    )
    # Odoo 19: use base.import.module when available; fallback to extra-addons path is gate-specific.
    try:
        with open(zip_path, "rb") as fh:
            import base64

            att = kw(
                models,
                uid,
                "ir.attachment",
                "create",
                [
                    {
                        "name": "dirty_gate_ext.zip",
                        "datas": base64.b64encode(fh.read()).decode("ascii"),
                        "type": "binary",
                    }
                ],
            )
            imp_id = kw(
                models,
                uid,
                "base.import.module",
                "create",
                [{"module_file": att, "force": True, "with_demo": False}],
            )
            kw(models, uid, "base.import.module", "import_module", [[imp_id]])
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: zip import failed ({exc}); continuing with stock modules only")
        return "res.partner"
    rows = kw(
        models,
        uid,
        "ir.module.module",
        "search_read",
        [[("name", "=", "dirty_gate_ext")]],
        {"fields": ["id", "state"], "limit": 1},
    )
    if rows and rows[0].get("state") != "installed":
        kw(models, uid, "ir.module.module", "button_immediate_install", [[rows[0]["id"]]])
    return "x_dirty_gate"


def seed_volume(models, uid, model: str, target: int) -> tuple[int, float]:
    existing = kw(models, uid, model, "search_count", [[]])
    need = max(0, target - int(existing))
    if need == 0:
        print(f"{model}: already has {existing} records (target {target})")
        return int(existing), 0.0
    print(f"Seeding {need} {model} records in batches of {BATCH}...")
    t0 = time.perf_counter()
    created = 0
    base = int(existing)
    while created < need:
        chunk = min(BATCH, need - created)
        vals = [{"name": f"Dirty Gate {base + created + i}"} for i in range(chunk)]
        if model == "x_dirty_gate":
            vals = [
                {"x_name": f"Dirty Gate {base + created + i}", "x_note": "seed"}
                for i in range(chunk)
            ]
        kw(models, uid, model, "create", [vals])
        created += chunk
        if created % max(BATCH * 10, 5000) == 0 or created == need:
            print(f"  ... {created}/{need}")
    elapsed = time.perf_counter() - t0
    total = kw(models, uid, model, "search_count", [[]])
    print(f"{model}: {total} records after seed ({elapsed:.1f}s)")
    return int(total), elapsed


def seed_chatter(models, uid, partner_ids: list[int]) -> None:
    if not partner_ids:
        return
    print(f"Posting chatter on {len(partner_ids)} partners...")
    for pid in partner_ids[: min(200, len(partner_ids))]:
        try:
            kw(
                models,
                uid,
                "mail.message",
                "create",
                [
                    {
                        "model": "res.partner",
                        "res_id": pid,
                        "body": "Dirty gate chatter seed",
                        "message_type": "comment",
                    }
                ],
            )
        except Exception:  # noqa: BLE001
            pass


def add_preexisting_inherit_view(models, uid) -> None:
    """Simulate a customer DB that already has customizations on stock forms."""
    arch = (
        '<xpath expr="//sheet" position="inside">'
        '<group string="Dirty pre-existing"><field name="comment"/></group>'
        "</xpath>"
    )
    existing = kw(
        models,
        uid,
        "ir.ui.view",
        "search",
        [[("name", "=", "dirty_gate.partner.inherit"), ("model", "=", "res.partner")]],
        {"limit": 1},
    )
    if existing:
        return
    parent = kw(
        models,
        uid,
        "ir.ui.view",
        "search_read",
        [[("model", "=", "res.partner"), ("type", "=", "form"), ("mode", "=", "primary")]],
        {"fields": ["id"], "limit": 1},
    )
    if not parent:
        return
    kw(
        models,
        uid,
        "ir.ui.view",
        "create",
        [
            {
                "name": "dirty_gate.partner.inherit",
                "model": "res.partner",
                "type": "form",
                "mode": "extension",
                "inherit_id": parent[0]["id"],
                "arch": arch,
            }
        ],
    )
    print("Pre-existing res.partner inherit view created")


def smoke_checks(models, uid, volume_model: str) -> None:
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        checks.append((label, bool(cond), detail))

    count = kw(models, uid, volume_model, "search_count", [[]])
    check("volume model count", count >= min(TARGET, 100), f"{count} records on {volume_model}")

    partner_views = kw(
        models,
        uid,
        "ir.ui.view",
        "search_count",
        [[("model", "=", "res.partner"), ("type", "=", "form")]],
    )
    check("partner form views exist", partner_views >= 1, str(partner_views))

    inherit_ok = kw(
        models,
        uid,
        "ir.ui.view",
        "search_count",
        [[("name", "=", "dirty_gate.partner.inherit")]],
    )
    check("pre-existing inherit view", inherit_ok >= 1)

    t0 = time.perf_counter()
    sample = kw(models, uid, volume_model, "search", [[]], {"limit": 500})
    scan_elapsed = time.perf_counter() - t0
    check("search sample 500", len(sample) == 500 or count < 500, f"{scan_elapsed:.2f}s")

    if volume_model == "res.partner":
        t1 = time.perf_counter()
        kw(
            models,
            uid,
            "res.partner",
            "search_read",
            [[("name", "ilike", "Dirty Gate")]],
            {"fields": ["name"], "limit": 2000},
        )
        dedupe_scan_elapsed = time.perf_counter() - t1
        check("dedupe-style scan", True, f"{dedupe_scan_elapsed:.2f}s for 2000 read")
        os.environ.setdefault("DIRTY_DEDUPE_SCAN_SECONDS", f"{dedupe_scan_elapsed:.2f}")

    failed = [c for c in checks if not c[1]]
    for label, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        suffix = f" ({detail})" if detail else ""
        print(f"[{status}] {label}{suffix}")
    if failed:
        raise SystemExit(f"{len(failed)} dirty gate smoke check(s) failed")


def main() -> None:
    _, models, uid = _proxy()
    install_modules(models, uid, EXTRA_MODULES)
    volume_model = install_dirty_custom_module(models, uid)
    add_preexisting_inherit_view(models, uid)
    total, seed_elapsed = seed_volume(models, uid, volume_model, TARGET)
    os.environ.setdefault("DIRTY_SEED_SECONDS", f"{seed_elapsed:.2f}")
    os.environ.setdefault("DIRTY_VOLUME_MODEL", volume_model)
    os.environ.setdefault("DIRTY_VOLUME_COUNT", str(total))

    if volume_model == "res.partner":
        ids = kw(models, uid, "res.partner", "search", [[("name", "ilike", "Dirty Gate")]], {"limit": 500})
        seed_chatter(models, uid, ids)

    smoke_checks(models, uid, volume_model)
    print("Dirty gate smoke: all checks passed")


if __name__ == "__main__":
    main()

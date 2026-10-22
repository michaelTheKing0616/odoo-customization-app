"""S11: the install step between the diagnosis and the build.

The design is made on the stock apps it needs, even when they are not
installed yet (planned installs). This module turns those planned installs
into one clear step the owner sees before building, and it is the code gate
that keeps Build and Apply closed until the apps are on the database.

AI proposes (the design's integrations); code authorizes: a module is only
listed when the design plans it AND the live snapshot says it is on disk but
not installed. Unknown snapshot -> the app stays pending (fails closed).
"""

from __future__ import annotations

from typing import Any

TITLE = "Install these apps before you build"
BLOCKED = (
    "Install the apps listed above first. Your design is built on them, "
    "so App Studio can't build or apply it until they are on your database."
)


def _label(module: str, fallback: str = "") -> str:
    try:
        from app.ai_host_install import MODULE_LABELS
    except Exception:  # noqa: BLE001
        MODULE_LABELS = {}
    if module in MODULE_LABELS:
        return MODULE_LABELS[module]
    try:
        from app.ai_conversation.stock_routing import DOMAIN_APPS
        hit = DOMAIN_APPS.get(module)
        if hit:
            return str(hit[0])
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.stock_app_install import STOCK_APPS
        for app in STOCK_APPS:
            if app.module == module:
                return app.label
    except Exception:  # noqa: BLE001
        pass
    if fallback and fallback != module:
        return fallback
    return module.replace("_", " ").title()


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def session_plans(understanding: Any, decision: Any, snap: Any) -> list[dict[str, Any]]:
    """Planned installs that are not app-design integrations (field packs on a stock host).

    - the understanding extends a stock host model that is missing from the snapshot
      (module from ``module_for_model``, version-aware);
    - a code-authorized stock check chose a stock app that needs installing.
    """
    out: list[dict[str, Any]] = []
    host = str(_get(understanding, "host_model", "") or "").strip()
    inherit = _get(understanding, "inherit_existing") in (True, "True", "true")
    index = dict(getattr(snap, "index", None) or {}) if snap is not None else {}
    if host and inherit and snap is not None and host not in index:
        try:
            from app.compat.odoo_versions import module_for_model
            mod = module_for_model(host, getattr(snap, "major", None) or None)
        except Exception:  # noqa: BLE001
            mod = None
        if mod:
            out.append({"module": mod, "app": "", "models": [host]})
    for sc in (_get(decision, "stock_checks", None) or []) if decision else []:
        mod = str(_get(sc, "install", "") or "").strip()
        if _get(sc, "choice") != "stock" or not mod:
            continue
        use = _get(sc, "use", None) or {}
        out.append({"module": mod, "app": str(_get(use, "name", "") or ""),
                    "models": [str(_get(use, "model", ""))] if _get(use, "model") else []})
    # Code-authorized reminders / follow-ups run as Odoo automation rules (base_automation).
    design = _get(understanding, "app_design", None) or {}
    wants_rules = bool(_get(design, "automations", None)) or any(
        _get(r, "decision") == "stock_automation" for r in (_get(design, "intent_contract", None) or [])) or any(
        # the approved checklist already authorized a record automation (before any design exists)
        _get(c, "shape") == "record_automation" and _get(c, "decision") == "authorize"
        for c in ((_get(decision, "capability", None) or []) if decision else []))
    if wants_rules and snap is not None:
        out.append({"module": "base_automation", "app": "", "models": [],
                    "why": "Your reminders and follow-ups run as automation rules."})
    return out


def planned_installs(design: Any, extra: Any = ()) -> list[dict[str, Any]]:
    """Integrations the design plans to install (installed False, status available), plus ``extra``."""
    out: list[dict[str, Any]] = []
    for e in extra or ():
        hit = next((o for o in out if o["module"] == e["module"]), None)
        if hit is None:
            out.append({"module": e["module"], "app": e.get("app") or "", "models": list(e.get("models") or []),
                        **({"why": e["why"]} if e.get("why") else {})})
        else:
            hit["models"] = list(dict.fromkeys(hit["models"] + list(e.get("models") or [])))
    for it in _get(design, "integrations", None) or []:
        mod = str(_get(it, "module", "") or "").strip()
        if not mod or _get(it, "installed") is not False:
            continue
        if str(_get(it, "status", "") or "") != "available":
            continue
        models = [str(m) for m in (_get(it, "models", None) or []) if str(m).strip()]
        hit = next((o for o in out if o["module"] == mod), None)
        if hit is not None:
            hit["models"] = list(dict.fromkeys(hit["models"] + models))
            continue
        out.append({"module": mod, "app": str(_get(it, "app", "") or ""), "models": models})
    return out


def pending_apps(design: Any, snap: Any, extra: Any = ()) -> list[dict[str, Any]]:
    """Planned installs still missing on the database, with a plain reason each.

    A module installed in ``snap.modules`` is done. Anything else stays pending,
    including when the snapshot is unknown (fails closed). ``installable`` is
    True only when the snapshot lists the module as on disk and uninstalled.
    """
    modules = dict(getattr(snap, "modules", None) or {}) if snap is not None else {}
    installable = dict(getattr(snap, "installable", None) or {}) if snap is not None else {}
    index = dict(getattr(snap, "index", None) or {}) if snap is not None else {}
    out = []
    for p in planned_installs(design, extra):
        mod = p["module"]
        if mod in modules:  # snapshot lists installed modules only (name -> version)
            continue
        label = _label(mod, p["app"])
        names = [index.get(m) or m for m in p["models"]]
        why = p.get("why") or (f"Your design builds on {label} ({', '.join(names[:3])})."
                               if names else f"Your design builds on {label}.")
        out.append({"module": mod, "label": label, "why": why, "models": p["models"],
                    "installable": mod in installable})
    return out


def install_step(design: Any, snap: Any, extra: Any = ()) -> dict[str, Any] | None:
    """Clarification block for the UI, or None when nothing is missing."""
    apps = pending_apps(design, snap, extra)
    if not apps:
        return None
    names = ", ".join(a["label"] for a in apps)
    can = all(a["installable"] for a in apps)
    message = (f"Your design uses {names}, which {'is' if len(apps) == 1 else 'are'} not installed yet. "
               "Install now, then build." if can else
               f"Your design uses {names}, but this database can't install "
               f"{'it' if len(apps) == 1 else 'all of them'} from here. Ask your Odoo administrator to install "
               f"{'it' if len(apps) == 1 else 'them'}, then check again.")
    return {"title": TITLE, "message": message, "apps": apps, "can_install": can,
            "install_label": "Install " + names if can else "Check again", "blocked_message": BLOCKED}


REFRESH_TITLE = "Update the design for the installed apps"
REFRESH_MESSAGE = ("The apps are installed. App Studio now updates your design to use their real "
                   "fields before you build.")
REFRESH_BLOCKED = "Update the design for the installed apps first, then build."
READ_ONLY_MESSAGE = ("This connection is read-only, so App Studio can't install apps on it. "
                     "Switch the connection to Standard in Connections, then come back and install.")


def refresh_step() -> dict[str, Any]:
    """Shown after the install while the design refresh is still to run (or to retry)."""
    return {"title": REFRESH_TITLE, "message": REFRESH_MESSAGE, "apps": [], "can_install": True,
            "install_label": "Update the design", "blocked_message": REFRESH_BLOCKED, "refresh": True}


def read_only_step(step: dict[str, Any]) -> dict[str, Any]:
    """Same step, Install disabled, with the read-only guidance up front."""
    out = dict(step)
    out.update(read_only=True, can_install=False, read_only_message=READ_ONLY_MESSAGE,
               blocked_message=READ_ONLY_MESSAGE)
    return out


def install_planned_module(port: Any, module: str, label: str) -> tuple[bool, str]:
    """Install one planned module through the change-set op ``module.install``.

    Callers authorize first (planned by the design AND installable in a fresh
    snapshot). Returns (ok, one plain sentence)."""
    from app.changeset.dispatch import DispatchError, dispatch_op
    from app.stock_app_install import _one_sentence

    try:
        dispatch_op(port, {"type": "module.install", "params": {"module": module}})
    except DispatchError as exc:
        return False, _one_sentence(label, str(exc))
    except Exception as exc:  # noqa: BLE001
        return False, _one_sentence(label, str(exc))
    return True, f"{label} is installed."

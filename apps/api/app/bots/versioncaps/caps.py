"""Lookups over the generated version catalogue. See package docstring."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from functools import cached_property, lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

DATA = Path(__file__).with_name("data")
MAJORS = (17, 18, 19, 20)
FITGAP_TABLE = Path(__file__).resolve().parents[1] / "fitgap" / "fitgap_table.json"
# Pulled in by Odoo itself on every database; a missing one is never "needs install".
ALWAYS = frozenset({"base", "web"})
# Reviewed: public model names of Enterprise apps (not in any Community catalogue), so a model
# alone grades enterprise-only without a module hint. Each module is in fitgap_table.json.
ENTERPRISE_MODELS: Mapping[str, str] = MappingProxyType(
    {
        "helpdesk.ticket": "helpdesk",
        "helpdesk.team": "helpdesk",
        "planning.slot": "planning",
        "documents.document": "documents",
        "sign.request": "sign",
        "sign.template": "sign",
        "quality.check": "quality_control",
        "quality.point": "quality_control",
        "quality.alert": "quality_control",
        "mrp.eco": "mrp_plm",
        "approval.request": "approvals",
        "approval.category": "approvals",
        "social.post": "social",
        "knowledge.article": "knowledge",
        "appointment.type": "appointment",
        "account.asset": "account_asset",
    }
)


@dataclass(frozen=True)
class Verdict:
    # installed-ok | available-needs-install | enterprise-only | not-in-this-version | unknown
    status: str
    reason: str
    module: str | None = None
    missing_depends: tuple[str, ...] = ()
    other_versions: tuple[int, ...] = ()
    missing_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if v not in (None, ())}
        for k in ("missing_depends", "other_versions", "missing_fields"):
            if k in d:
                d[k] = list(d[k])
        return d


@dataclass
class Caps:
    """One version's catalogue. ``data`` is the decoded generator output."""

    major: int
    data: Mapping[str, Any]
    enterprise: Mapping[str, Any] = field(default_factory=dict)

    @property
    def listed(self) -> Mapping[str, Any]:
        return self.data.get("modules", {})

    @cached_property
    def modules(self) -> Mapping[str, Any]:
        """Introspected modules only (installed on the generation sandbox)."""
        return {k: v for k, v in self.listed.items() if v.get("state", "installed") == "installed"}

    @property
    def models(self) -> Mapping[str, Any]:
        return self.data.get("models", {})

    @cached_property
    def blocked(self) -> frozenset[str]:
        rest = {k for k in self.listed if k not in self.modules and k not in self.enterprise}
        return frozenset(self.data.get("not_introspectable", ())) | rest


@lru_cache(maxsize=1)
def _enterprise() -> dict[str, Any]:
    try:
        return json.loads(FITGAP_TABLE.read_text()).get("enterprise_modules", {})
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=8)
def _load_file(major: int) -> Caps | None:
    p = DATA / f"caps_{major}.json.gz"
    try:
        d = json.loads(gzip.decompress(p.read_bytes()))
    except (OSError, ValueError, EOFError):  # missing, truncated, not gzip, bad JSON
        return None
    if not _shape_ok(d) or d.get("major") != major or not _prov_ok(d.get("provenance"), major):
        return None
    return Caps(major, d, _enterprise())


_PROV_KEYS = ("major", "edition", "generated", "source_image", "image_id", "generator", "sources")


def _prov_ok(p: Any, major: int) -> bool:
    """A catalogue without provenance (version, date, source image) is not trusted."""
    if not isinstance(p, dict) or any(not p.get(k) for k in _PROV_KEYS):
        return False
    try:
        date.fromisoformat(str(p["generated"]))
    except ValueError:
        return False
    return (
        p["major"] == major
        and p["source_image"] == f"odoo:{major}"
        and str(p["image_id"]).startswith("sha256:")
        and isinstance(p["sources"], list)
    )


def provenance(major: Any) -> dict[str, Any] | None:
    """Where ``major``'s catalogue came from (copy), or None when there is no trusted file."""
    c = load(major)
    p = c.data.get("provenance") if c else None
    return dict(p) if isinstance(p, dict) else None


def _shape_ok(d: Any) -> bool:
    if not isinstance(d, dict):
        return False
    mods, models = d.get("modules"), d.get("models")
    if not isinstance(mods, dict) or not isinstance(models, dict) or not models:
        return False
    if not isinstance(d.get("not_introspectable", []), list):
        return False
    for m in mods.values():
        if not isinstance(m, dict) or not isinstance(m.get("depends", []), list):
            return False
    for m in models.values():
        if not isinstance(m, dict) or not isinstance(m.get("fields"), dict):
            return False
        if not isinstance(m.get("modules", []), list):
            return False
        for row in m["fields"].values():
            if not isinstance(row, list) or len(row) not in (4, 5) or not isinstance(row[3], list):
                return False
    return True


_OVERRIDE: dict[int, Caps | None] = {}


def load(major: Any) -> Caps | None:
    """Catalogue for ``major`` or None (fail closed). Tests may inject via ``_OVERRIDE``."""
    if type(major) is not int:  # plain int major only: '17', 17.0, '17.x', True are refused
        return None
    m = major
    if m in _OVERRIDE:
        return _OVERRIDE[m]
    return _load_file(m) if m in MAJORS else None


def _ent(c: Caps, name: str) -> bool:
    e = c.enterprise.get(name)
    return bool(e) and c.major >= int(e.get("min_major", 0) or 0) and name not in c.modules


def module_info(version: Any, name: str) -> dict[str, Any] | None:
    c = load(version)
    if c is None:
        return None
    if name in c.blocked:
        return {
            "name": name,
            "edition": "community",
            "introspected": False,
            "note": "listed but not introspectable; fields not verifiable",
            **c.listed.get(name, {}),
        }
    m = c.modules.get(name)
    if m is not None:
        return {"name": name, "edition": "community", "introspected": True, **m}
    if _ent(c, name):
        return {
            "name": name,
            "edition": "enterprise",
            "introspected": False,
            "note": "enterprise-only; fields not verifiable",
        }
    return None


def cron_owner(version: Any, name: Any) -> str | None:
    """The one app that owns scheduled action ``name`` in stock ``version``: the module whose
    xml id names it (generator, ir.model.data), else, for a scheduled action Odoo creates per
    record at runtime, the app defining the model of the one matching probed template
    ("cron_templates", e.g. "Lunch: send automatic email to {}"). None when unknown or
    ambiguous (fail closed)."""
    c = load(version)
    if c is None or not isinstance(name, str):
        return None
    mods = c.data.get("crons", {}).get(name)
    if mods is not None:
        ok = isinstance(mods, list) and len(mods) == 1 and isinstance(mods[0], str)
        return mods[0] if ok else None
    hits = {
        t["model"]
        for t in c.data.get("cron_templates", [])
        if isinstance(t, dict) and _template_match(t.get("template"), name)
    }
    if len(hits) != 1:
        return None
    m = c.models.get(next(iter(hits)))
    return _definer(c, list(m.get("modules", ()))) if m else None


def _template_match(template: Any, name: str) -> bool:
    """``template`` has one "{}" for the record's name; ``name`` may carry a placeholder
    such as "{supplier}" (catalogue) or a real record name (runtime)."""
    if not isinstance(template, str) or template.count("{}") != 1:
        return False
    head, tail = template.split("{}")
    mid = name[len(head) : len(name) - len(tail) if tail else None]
    return name.startswith(head) and name.endswith(tail) and bool(mid.strip())


def model_info(version: Any, model: str) -> dict[str, Any] | None:
    c = load(version)
    m = c and c.models.get(model)
    if not m:
        return None
    mods = list(m.get("modules", ()))
    return {
        "model": model,
        "defined_by_module": _definer(c, mods),
        "modules": mods,
        "installed_by_default": any(x in ALWAYS for x in mods),
        "transient": bool(m.get("transient")),
    }


def _definer(c: Caps, mods: list[str]) -> str | None:
    """The module that introduces a model/field: the one whose depends closure covers the others."""
    if not mods:
        return None
    for cand in mods:
        clo = _closure(c, cand)
        if all(x == cand or x not in clo for x in mods):  # cand depends on none of the others
            if all(cand in _closure(c, x) or x == cand for x in mods):
                return cand
    return sorted(mods, key=lambda x: len(_closure(c, x)))[0]


def _closure(c: Caps, name: str) -> frozenset[str]:
    seen: set[str] = set()
    stack = [name]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend((c.modules.get(n) or {}).get("depends", ()))
    return frozenset(seen)


def field_info(version: Any, model: str, fname: str) -> dict[str, Any] | None:
    c = load(version)
    m = c and c.models.get(model)
    row = m and m.get("fields", {}).get(fname)
    if not row:
        return None
    out = {
        "model": model,
        "field": fname,
        "type": row[0],
        "relation": row[1] or None,
        "required": bool(row[2]),
        "modules": list(row[3]),
        "module": _definer(c, list(row[3])),
    }
    if len(row) > 4:
        out["selection"] = list(row[4])
    return out


def find_module_for(version: Any, model: str, fname: str | None = None) -> str | None:
    i = field_info(version, model, fname) if fname else model_info(version, model)
    return (i or {}).get("module" if fname else "defined_by_module")


def _versions_with(model: str, fname: str | None, skip: int) -> tuple[int, ...]:
    out = []
    for v in MAJORS:
        if v == skip:
            continue
        c = load(v)
        m = c and c.models.get(model)
        if m and (fname is None or fname in m.get("fields", {})):
            out.append(v)
    return tuple(out)


def availability(
    version: Any,
    edition: Any,
    installed_modules: Any,
    model: Any,
    fields: Any = (),
    module_hint: Any = None,
) -> Verdict:
    """Can ``model`` (+``fields``) exist in stock Odoo ``version``/``edition``; what to install.
    Never raises: odd input or a catalogue fault -> ``unknown``."""
    bad = Verdict("unknown", "invalid input for capability check; nothing verified")
    if not isinstance(model, str) or not model or not isinstance(edition, str):
        return bad
    if isinstance(installed_modules, (str, bytes)) or not isinstance(
        installed_modules, (list, tuple, set, frozenset)
    ):
        return bad
    if isinstance(fields, (str, bytes)) or not isinstance(fields, (list, tuple, set, frozenset)):
        return bad
    if not all(isinstance(x, str) for x in [*installed_modules, *fields]):
        return bad
    if module_hint is not None and not isinstance(module_hint, str):
        return bad
    fields = [f for f in fields if not f.startswith("x_")]  # custom/Studio: no catalogue claim
    try:
        return _availability(version, edition, installed_modules, model, fields, module_hint)
    except Exception:  # noqa: BLE001 - fail closed on any catalogue fault
        return Verdict("unknown", "capability catalogue error; nothing verified")


def _availability(version, edition, installed_modules, model, fields, module_hint) -> Verdict:
    c = load(version)
    if c is None:
        return Verdict("unknown", f"no capability data for Odoo {version}; nothing verified")
    inst = frozenset(installed_modules) | ALWAYS
    ent_db = str(edition).lower().startswith("ent")
    fields = sorted(set(fields))
    m = c.models.get(model)
    if m is None:
        module_hint = module_hint or ENTERPRISE_MODELS.get(model)
        hint = module_hint if module_hint and _ent(c, module_hint) else None
        if hint:
            return _ent_verdict(c, hint, ent_db, inst, model)
        if module_hint and module_hint in c.blocked:
            return Verdict(
                "unknown",
                f"module {module_hint} could not be introspected on Odoo {c.major}",
                module_hint,
            )
        others = _versions_with(model, None, c.major)
        where = f"; exists in {', '.join(map(str, others))}" if others else ""
        if c.blocked or c.enterprise:  # an unread/Enterprise module could still provide it
            return Verdict(
                "unknown",
                f"model {model} not found in Odoo {c.major} Community catalogue{where}; may "
                "come from an Enterprise or non-introspected module; not verifiable",
                other_versions=others,
            )
        return Verdict(
            "not-in-this-version",
            f"model {model} is not in stock Odoo {c.major}{where}",
            other_versions=others,
        )
    need = {}
    missing_f = []
    for f in fields:
        row = m.get("fields", {}).get(f)
        if row is None:
            missing_f.append(f)
        else:
            need[f] = _definer(c, list(row[3]))
    if missing_f:
        others = tuple(
            v
            for v in MAJORS
            if v != c.major
            and all(
                f in ((load(v) or Caps(v, {})).models.get(model, {}).get("fields", {}))
                for f in missing_f
            )
        )
        return Verdict(
            "not-in-this-version",
            f"field(s) {', '.join(missing_f)} not on {model} in stock Odoo {c.major} Community"
            + (f"; exist in {', '.join(map(str, others))}" if others else ""),
            missing_fields=tuple(missing_f),
            other_versions=others,
        )
    mods = {_definer(c, list(m.get("modules", ())))} | set(need.values())
    mods.discard(None)
    todo = sorted(x for x in mods if x not in inst)
    if not todo:
        return Verdict(
            "installed-ok",
            f"{model} available with installed modules",
            next(iter(sorted(mods)), None),
        )
    miss: list[str] = []
    for t in todo:
        if t in c.blocked:
            return Verdict("unknown", f"module {t} could not be introspected on Odoo {c.major}", t)
        miss.extend(x for x in sorted(_closure(c, t)) if x not in inst and x not in miss)
    main = todo[-1] if len(todo) == 1 else ",".join(todo)
    return Verdict(
        "available-needs-install",
        f"available in Odoo {c.major} via module {main}; needs install"
        + (
            f" (with {', '.join(x for x in miss if x not in todo)})"
            if len(miss) > len(todo)
            else ""
        ),
        main,
        tuple(miss),
    )


def _ent_verdict(c: Caps, name: str, ent_db: bool, inst: frozenset[str], model: str) -> Verdict:
    if ent_db and name in inst:
        return Verdict(
            "unknown",
            f"{model} from Enterprise module {name}: installed, fields not verifiable "
            "from catalogue; read the live database",
            name,
        )
    if ent_db:  # an Enterprise database that does not have the app yet: install it
        return Verdict(
            "available-needs-install",
            f"{model} needs Enterprise module {name}, not installed on this Enterprise "
            "database; needs install (fields and dependencies not verifiable from catalogue)",
            name,
            (name,),
        )
    return Verdict(
        "enterprise-only",
        f"{model} needs Enterprise module {name}; fields not verifiable; "
        "this is a Community database",
        name,
    )


def install_reason(
    version: Any,
    edition: str,
    installed: Iterable[str],
    model: str,
    fields: Iterable[str] = (),
    module_hint: str | None = None,
) -> str | None:
    """Adapter for configverify/variance cannot-read reasons: text or None when nothing to add."""
    v = availability(version, edition, installed, model, fields, module_hint)
    return None if v.status == "installed-ok" else v.reason

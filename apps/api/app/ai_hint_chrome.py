"""Hint chrome — AST / Must-do status hints as form decoration (any grain).

Status-hint / banner / alert / ribbon rows from the constraint AST (or locked
Must-do) become form chrome: preview banners + Apply IR alert/ribbon widgets.
They must never materialize as Char fields. Placement hints ("Place under …")
stay non-chrome. No Sales-only branches.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any
from xml.sax.saxutils import escape, quoteattr

# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


@dataclass
class HintChrome:
    """One operator-facing form decoration derived from a Must-do / AST hint."""

    message: str
    level: str = "warning"  # info | warning | danger
    invisible: str | None = None  # Odoo 17+ Python expr (hide when true)
    source: str = ""
    kind: str = "alert"  # alert | ribbon

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Extraction — root for ALL hints (Prefer + residual + any grain)
# ---------------------------------------------------------------------------

_STATUS_HINT_BULLET_RE = re.compile(
    r"(?i)^(?:constraint:\s*)?(?:status\s+hint|banner|alert|ribbon|decoration)\s+when\s+(.+)$"
)
_STATUS_HINT_PROSE_RE = re.compile(
    r"(?i)\b(?:show|display)\s+(?:a\s+)?(?:status\s+hint|banner|alert|decoration|ribbon)"
    r"\s+when\s+(.+?)(?:\.|$)"
)
_PLACE_HINT_RE = re.compile(r"(?i)^place\s+under\b|^under\s+.+\s+group$")
_RIBBON_RE = re.compile(r"(?i)\bribbon\b")


def _clean_cond(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "")).strip(" .;:")
    text = re.sub(r"(?i)^the\s+", "", text).strip()
    return text[:200]


def _message_from_cond(cond: str) -> str:
    """Operator-facing banner copy — sentence case, no 'Status hint when' prefix."""
    cond = _clean_cond(cond)
    if not cond:
        return "Status notice"
    if re.search(r"(?i)\bpo\b.*delivery\s+window", cond) or re.search(
        r"(?i)delivery\s+window.*incomplete", cond
    ):
        return "Customer PO is set but the delivery window is incomplete"
    return cond[:1].upper() + cond[1:]


def _level_for(cond: str, *, kind: str) -> str:
    if kind == "ribbon":
        return "info"
    low = cond.lower()
    if any(w in low for w in ("danger", "blocked", "overdue", "cancel", "fail")):
        return "danger"
    if any(w in low for w in ("incomplete", "missing", "required", "warn", "but")):
        return "warning"
    return "info"


def collect_status_hint_rows(
    *,
    prompt: str = "",
    constraints: list[str] | None = None,
    hints: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Return (source_row, condition) for every status/banner/alert/ribbon hint."""
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _add(source: str, cond: str) -> None:
        cond_c = _clean_cond(cond)
        if len(cond_c) < 4:
            return
        key = cond_c.lower()
        if key in seen:
            return
        seen.add(key)
        rows.append((source.strip(), cond_c))

    for raw in list(hints or []) + list(constraints or []):
        text = str(raw or "").strip()
        if not text or _PLACE_HINT_RE.search(text):
            continue
        m = _STATUS_HINT_BULLET_RE.match(text)
        if m:
            _add(text, m.group(1))
            continue
        m = _STATUS_HINT_PROSE_RE.search(text)
        if m:
            _add(text, m.group(1))

    if prompt:
        for m in _STATUS_HINT_PROSE_RE.finditer(prompt):
            _add(m.group(0).strip(), m.group(1))

    return rows


def _field_names(draft: dict[str, Any]) -> dict[str, str]:
    """Map lowercase label/name tokens → technical field name."""
    out: dict[str, str] = {}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "").strip()
            if not name:
                continue
            out[name.lower()] = name
            label = str(field.get("string") or "").strip().lower()
            if label:
                out[label] = name
                out[re.sub(r"[^a-z0-9]+", " ", label).strip()] = name
            leaf = name[2:] if name.startswith("x_") else name
            out[leaf.replace("_", " ")] = name
    return out


def _guess_invisible(cond: str, fields: dict[str, str]) -> str | None:
    """Best-effort Odoo invisible expr from common Prefer / residual patterns."""
    low = cond.lower()

    def find(*needles: str) -> str | None:
        for needle in needles:
            for key, name in fields.items():
                if needle in key:
                    return name
        return None

    po = find(
        "customer po",
        "po reference",
        "customer_po",
        "purchase order ref",
    )
    start = find(
        "delivery window start",
        "window start",
        "delivery_window_start",
    )
    end = find(
        "delivery window end",
        "window end",
        "delivery_window_end",
    )

    if po and (start or end) and (
        "incomplete" in low or ("po" in low and "delivery" in low)
    ):
        parts = [f"not {po}"]
        if start and end:
            parts.append(f"({start} and {end})")
        elif start:
            parts.append(start)
        elif end:
            parts.append(end)
        return " or ".join(parts)

    for key, name in fields.items():
        token = key.replace(" ", "_")
        if key in low or token in low.replace(" ", "_"):
            if re.search(r"(?i)\b(missing|empty|not\s+set|unset|blank)\b", low):
                return name
            if re.search(r"(?i)\b(set|present|filled|true|checked)\b", low):
                return f"not {name}"
    return None


def hints_to_chrome(
    *,
    prompt: str = "",
    constraints: list[str] | None = None,
    hints: list[str] | None = None,
    draft: dict[str, Any] | None = None,
) -> list[HintChrome]:
    """Build chrome rows from AST hints / Must-do / brief — never fields."""
    field_index = _field_names(draft or {})
    chrome: list[HintChrome] = []
    for source, cond in collect_status_hint_rows(
        prompt=prompt, constraints=constraints, hints=hints
    ):
        kind = "ribbon" if _RIBBON_RE.search(source) or _RIBBON_RE.search(cond) else "alert"
        chrome.append(
            HintChrome(
                message=_message_from_cond(cond),
                level=_level_for(cond, kind=kind),
                invisible=_guess_invisible(cond, field_index),
                source=source,
                kind=kind,
            )
        )
    return chrome


# ---------------------------------------------------------------------------
# Apply IR — alert / ribbon widgets (not Char fields)
# ---------------------------------------------------------------------------

_ALERT_CLASS = {
    "info": "alert alert-info",
    "warning": "alert alert-warning",
    "danger": "alert alert-danger",
}


def render_hint_arch_nodes(chrome: list[HintChrome]) -> str:
    """XML nodes suitable for injection inside an inherit ``//sheet`` xpath."""
    bits: list[str] = []
    for row in chrome:
        msg = escape(row.message)
        if row.kind == "ribbon":
            bg = {
                "info": "text-bg-info",
                "warning": "text-bg-warning",
                "danger": "text-bg-danger",
            }.get(row.level, "text-bg-info")
            inv = f" invisible={quoteattr(row.invisible)}" if row.invisible else ""
            bits.append(
                f'      <widget name="web_ribbon" title={quoteattr(row.message)} '
                f"bg_color={quoteattr(bg)}{inv}/>"
            )
            continue
        cls = _ALERT_CLASS.get(row.level, "alert alert-warning")
        inv = f" invisible={quoteattr(row.invisible)}" if row.invisible else ""
        bits.append(
            f"      <div class={quoteattr(cls)} role=\"alert\""
            f" name={quoteattr('ingenium_hint_chrome')}{inv}>\n"
            f"        {msg}\n"
            "      </div>"
        )
    return "\n".join(bits)


def _inject_sheet_chrome(arch: str, nodes: str) -> str:
    """Append a //sheet inside xpath with alert/ribbon nodes; idempotent."""
    if not nodes.strip():
        return arch
    arch = re.sub(
        r'\s*<xpath expr="//sheet" position="inside">\s*'
        r'(?:<div class="alert[^"]*" role="alert" name="ingenium_hint_chrome"[^>]*>.*?</div>\s*|'
        r'<widget name="web_ribbon"[^/]*/>\s*)+'
        r"</xpath>",
        "",
        arch,
        flags=re.I | re.S,
    )
    block = f'  <xpath expr="//sheet" position="inside">\n{nodes}\n  </xpath>'
    if "</data>" in arch:
        return arch.replace("</data>", block + "\n</data>", 1)
    if arch.strip().startswith("<data"):
        return arch.rstrip() + "\n" + block + "\n</data>"
    return f"<data>\n{arch}\n{block}\n</data>"


def _dedupe_rows(rows: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        key = row.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row.strip())
    return out


def _constraints_from_draft(draft: dict[str, Any], prompt: str) -> tuple[list[str], list[str]]:
    constraints: list[str] = []
    hints: list[str] = []
    understanding = draft.get("_understanding")
    if isinstance(understanding, dict):
        raw = understanding.get("constraints")
        if isinstance(raw, list):
            constraints.extend(str(x) for x in raw if str(x).strip())
    try:
        from app.ai_conversation.understand import parse_locked_diagnosis

        locked = parse_locked_diagnosis(prompt)
        if locked is not None:
            constraints.extend(locked.constraints)
    except Exception:  # noqa: BLE001
        pass
    ast = draft.get("_constraint_ast")
    if isinstance(ast, dict) and isinstance(ast.get("hints"), list):
        hints.extend(str(x) for x in ast["hints"] if str(x).strip())
    elif hasattr(ast, "hints"):
        hints.extend(str(x) for x in (getattr(ast, "hints") or []) if str(x).strip())
    if not hints:
        try:
            from app.ai_constraint_ast import parse_det

            host = None
            for model in draft.get("models") or []:
                if isinstance(model, dict) and str(model.get("mode") or "") == "inherit":
                    host = str(model.get("model") or "") or None
                    break
            det = parse_det(prompt, host=host, inherit=bool(host), grain="field_pack")
            hints.extend(list(det.hints or []))
        except Exception:  # noqa: BLE001
            pass
    return _dedupe_rows(constraints), _dedupe_rows(hints)


def apply_hint_chrome(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Stamp preview chrome + inject Apply IR alert/ribbon nodes. Never add Char fields."""
    if draft.get("_capability_primary_option_a"):
        return []
    user_prompt = prompt or str(
        draft.get("_user_prompt") or draft.get("_user_prompt") or ""
    )
    constraints, hints = _constraints_from_draft(draft, user_prompt)
    chrome = hints_to_chrome(
        prompt=user_prompt,
        constraints=constraints,
        hints=hints,
        draft=draft,
    )
    if not chrome:
        draft.pop("_hint_chrome", None)
        return []

    draft["_hint_chrome"] = [c.to_dict() for c in chrome]
    notes = [f"hint_chrome: {len(chrome)} decoration(s)"]

    nodes = render_hint_arch_nodes(chrome)
    if not nodes.strip():
        return notes

    host = None
    for model in draft.get("models") or []:
        if isinstance(model, dict) and str(model.get("mode") or "") == "inherit":
            host = str(model.get("model") or "") or None
            break

    if not host:
        for view in draft.get("views") or []:
            if not isinstance(view, dict) or str(view.get("type") or "") != "form":
                continue
            arch = str(view.get("arch") or "")
            if not arch or "<sheet" not in arch:
                continue
            view["arch"] = re.sub(
                r"(<sheet\b[^>]*>)",
                r"\1\n" + nodes,
                arch,
                count=1,
                flags=re.I,
            )
            notes.append("hint_chrome: injected into residual form arch")
            return notes
        return notes

    target = None
    for view in draft.get("views") or []:
        if not isinstance(view, dict):
            continue
        if (
            str(view.get("model") or "") == host
            and str(view.get("type") or "form") == "form"
            and str(view.get("mode") or "") in {"extension", "inherit", ""}
        ):
            target = view
            break
    if target is None:
        notes.append("hint_chrome: no form extension to decorate")
        return notes
    arch = str(target.get("arch") or "")
    target["arch"] = _inject_sheet_chrome(arch, nodes)
    notes.append(f"hint_chrome: applied on {host}")
    return notes


def attach_preview_alerts(
    form_preview: dict[str, Any] | None,
    draft: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Stamp ``alerts`` onto a PreviewFormView dict for canvas chrome."""
    if not isinstance(form_preview, dict):
        return form_preview
    chrome_rows: list[dict[str, Any]] = []
    if isinstance(draft, dict):
        raw = draft.get("_hint_chrome")
        if isinstance(raw, list):
            chrome_rows = [r for r in raw if isinstance(r, dict) and r.get("message")]
    if not chrome_rows:
        form_preview.setdefault("alerts", [])
        return form_preview
    alerts: list[dict[str, Any]] = []
    for row in chrome_rows:
        # Single banner line: condition lives in ``message`` only.
        # Never stamp a redundant ``when`` echo (UI used to render
        # title + "When: …" with the same condition twice).
        alerts.append(
            {
                "id": f"hint_{len(alerts)}",
                "level": str(row.get("level") or "warning"),
                "message": str(row.get("message") or ""),
                "when": None,
                "kind": str(row.get("kind") or "alert"),
            }
        )
    form_preview["alerts"] = alerts
    return form_preview


__all__ = [
    "HintChrome",
    "apply_hint_chrome",
    "attach_preview_alerts",
    "collect_status_hint_rows",
    "hints_to_chrome",
    "render_hint_arch_nodes",
]

"""Hybrid constraint AST for Diagnosis Must-do — any grain, any prompt.

Deterministic floor (parse_det) always produces a complete baseline from
structural anchors (host/grain/inherit, high-precision field cues, date-range,
status-hint, no-new-app, full_app model+fields). Optional Flash/constrained
JSON (parse_llm) fills free prose into the same AST shape. Merge never shrinks
below the det floor. Regex is an anchor inside det parse — not the only brain.

No Sales-only or Visitor-only branches.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# AST shape
# ---------------------------------------------------------------------------


@dataclass
class ConstraintField:
    """One field the brief requires."""

    label: str
    ttype: str = "char"  # char|text|boolean|date|datetime|selection|many2one|…
    relation: str | None = None
    selection_options: str | None = None
    # Prefer bare date rows (no "Field:" prefix) so IR date inference works.
    bare: bool = False


@dataclass
class ConstraintAST:
    """Structured Must-do constraints — grain-agnostic."""

    grain: str = "full_app"
    host: str | None = None
    host_label: str | None = None
    fields: list[ConstraintField] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    # full_app residual model
    model_id: str | None = None
    model_label: str | None = None
    structural: list[str] = field(default_factory=list)  # Menu / List+form / …
    uncertain: bool = False
    source: str = "det"  # det | llm | mixed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Shared anchors (regex as structural cues inside det parse)
# ---------------------------------------------------------------------------

_NO_NEW_APP_RE = re.compile(
    r"(?i)\b(?:do\s+not|don't|never)\s+(?:create|invent|build)\s+(?:a\s+)?"
    r"(?:new\s+|parallel\s+)?(?:home[- ]?screen\s+)?(?:[A-Za-z][\w-]*\s+)?app\b|"
    r"\bno\s+new\s+(?:home[- ]?screen\s+)?app\b|"
    r"\bnot\s+a\s+new\s+(?:home[- ]?screen\s+)?app\b|"
    r"\bdo\s+not\s+invent\b|"
    r"\bprefer\s+(?:inherit|extend)\b"
)
_UNDER_GROUP_RE = re.compile(
    r"(?i)\bunder\s+(?:(?:the|a|an)\s+)?([A-Za-z][\w /&-]{0,40}?)\s+group\b"
)
_LEADING_ARTICLE_RE = re.compile(r"(?i)^(a|an|the)\s+")
_CHECKBOX_FIELD_RE = re.compile(
    r"(?i)\bcheckbox\s+[\"']?([^\"',.;]+?)[\"']?"
    r"(?=\s+and\b|\s+under\b|\s+on\b|,|\.|$)"
)
_TYPED_TEXT_FIELD_RE = re.compile(
    r"(?i)(?:\badd\b|\band\b|,)\s+([A-Z][\w /&-]{1,40}?)\s+text(?:\s+field)?\b"
)
_ADD_CLAUSE_RE = re.compile(
    r"(?i)\badd\s+(?:a\s+|an\s+)?(?!checkbox\b|boolean\b)"
    r"(.+?)(?="
    r"\.\s*(?:On\s+the\s+form|Prefer|Do\s+not|Don't|Show\s+a\s+|When\b)|"
    r"\.\s*$|;\s*|\n|$)"
)
_DATE_RANGE_PAREN_RE = re.compile(
    r"(?i)\(\s*(?:a\s+)?"
    r"(?:date\s*range(?:\s+or\s+start\s*/\s*end(?:\s+dates?)?)?|"
    r"start\s*/\s*end(?:\s+dates?)?|"
    r"start\s+and\s+end(?:\s+dates?)?|"
    r"start\s+or\s+end(?:\s+dates?)?)"
    r"[^)]*\)\s*$"
)
_STATUS_HINT_RE = re.compile(
    r"(?i)\b(?:show|display)\s+(?:a\s+)?(?:status\s+hint|banner|alert|decoration|ribbon)"
    r"\s+when\s+(.+?)(?:\.|$)"
)
_FIELD_CHUNK_NOISE_RE = re.compile(
    r"(?i)^(a|an|the|add|checkbox|boolean|text(?:\s+field)?)\s+"
)
_TRAILING_AND_RE = re.compile(r"(?i)\s+\band\b\s*$")
_PRONOUN_LABELS = frozenset(
    {"it", "this", "that", "them", "one", "field", "a field", "the field"}
)

_APP_NOUN_RE = re.compile(
    r"(?i)\b(?:build|create|make)\s+(?:an?\s+)?(?:(?:tiny|simple|small|new|mini)\s+)*"
    r"(.+?)\s+app\b"
    r"|^([A-Z][\w][\w\s/-]{1,48}?)(?:\s+for\s+(?:our|the|a)\b|\s*[:—-])"
)
_MODEL_WITH_FIELDS_RE = re.compile(
    r"(?i)\bmodel\s+with\s+(.+?)(?:\.\s*(?:Simple|No\s+workflow|Menu)|;|\.|$)"
)
_MENU_UNDER_RE = re.compile(r"(?i)\bmenu\s+under\s+([A-Za-z][\w\s]{0,40})")
_CREATE_READ_ONLY_RE = re.compile(
    r"(?i)\b(?:no\s+workflow\s+beyond\s+)?create\s*/\s*read\b|create\s+and\s+read\s+only"
)
_LIST_FORM_RE = re.compile(r"(?i)\blist\s*(?:\+|and|&)\s*forms?\b")

_FIELD_TYPE_HINTS = frozenset(
    {
        "char",
        "text",
        "html",
        "boolean",
        "checkbox",
        "integer",
        "int",
        "float",
        "monetary",
        "binary",
        "image",
        "date",
        "datetime",
        "many2one",
        "many2many",
        "one2many",
        "selection",
    }
)

_MUST_DO_CAP = 12


def _dedupe_strs(rows: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        key = row.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row.strip())
    return out


def _norm_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip().lower())


# ---------------------------------------------------------------------------
# Prefer / field_pack anchors
# ---------------------------------------------------------------------------


def split_conjunction_chunks(body: str) -> list[str]:
    """Split field lists on commas / 'and' while keeping parentheticals intact."""
    chunks: list[str] = []
    buf = ""
    depth = 0
    for ch in body or "":
        if ch == "(":
            depth += 1
            buf += ch
        elif ch == ")":
            depth = max(0, depth - 1)
            buf += ch
        elif ch == "," and depth == 0:
            if buf.strip():
                chunks.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        chunks.append(buf.strip())
    normalized: list[str] = []
    for chunk in chunks:
        if re.search(r"(?i)\band\b", chunk) and "(" not in chunk:
            parts = re.split(r"(?i)\s+and\s+", chunk)
            normalized.extend(p.strip(" .") for p in parts if p.strip())
        else:
            if re.match(r"(?i)^and\s+", chunk):
                chunk = re.sub(r"(?i)^and\s+", "", chunk).strip()
            if re.search(r"(?i)\band\b", chunk):
                parts: list[str] = []
                part = ""
                d = 0
                i = 0
                low = chunk
                while i < len(low):
                    c = low[i]
                    if c == "(":
                        d += 1
                        part += c
                        i += 1
                    elif c == ")":
                        d = max(0, d - 1)
                        part += c
                        i += 1
                    elif d == 0 and low[i : i + 5].lower() == " and ":
                        if part.strip():
                            parts.append(part.strip())
                        part = ""
                        i += 5
                    else:
                        part += c
                        i += 1
                if part.strip():
                    parts.append(part.strip())
                if len(parts) > 1:
                    normalized.extend(parts)
                    continue
            normalized.append(chunk.strip(" ."))
    return [c for c in normalized if c]


def expand_field_chunk(chunk: str) -> list[str]:
    """One add-list chunk → one or more field labels (date-range → start/end)."""
    raw = re.sub(r"\s+", " ", (chunk or "")).strip(" .")
    raw = _FIELD_CHUNK_NOISE_RE.sub("", raw).strip()
    raw = _TRAILING_AND_RE.sub("", raw).strip(" .")
    if not raw or len(raw) < 3:
        return []
    low = raw.lower()
    if low in _PRONOUN_LABELS or low in {
        "checkbox",
        "boolean",
        "text",
        "field",
        "a field",
        "the field",
    }:
        return []
    raw = re.split(r"(?i)\s+under\s+", raw, maxsplit=1)[0].strip()
    m = _DATE_RANGE_PAREN_RE.search(raw)
    if m:
        base = raw[: m.start()].strip(" .")
        base = re.sub(r"(?i)\s*\([^)]*\)\s*$", "", base).strip()
        base = _TRAILING_AND_RE.sub("", base).strip(" .")
        if not base or len(base) < 3:
            return []
        return [f"{base} start date", f"{base} end date"]
    raw = re.sub(
        r"(?i)\s*\(\s*(?:char|text|html|boolean|checkbox|integer|int|float|"
        r"monetary|binary|image|date|datetime|many2one|selection)\s*\)\s*$",
        "",
        raw,
    ).strip(" .")
    if not raw or len(raw) < 3:
        return []
    return [raw]


def iter_add_field_labels(text: str) -> list[str]:
    """All Prefer/field_pack labels after add — conjunction + date-range aware."""
    labels: list[str] = []
    for m in _ADD_CLAUSE_RE.finditer(text or ""):
        body = m.group(1).strip()
        body = re.split(
            r"(?i)\s+(?:under\s+(?:the\s+)?[\w /&-]+?\s+group|"
            r"required\s+before\b|on\s+the\s+\w+\s+form)\b",
            body,
            maxsplit=1,
        )[0].strip()
        for chunk in split_conjunction_chunks(body):
            labels.extend(expand_field_chunk(chunk))
    return _dedupe_strs(labels)


def _infer_ttype(label: str, *, stated: str | None = None) -> str:
    if stated:
        s = stated.lower().strip()
        if s in _FIELD_TYPE_HINTS:
            if s == "checkbox":
                return "boolean"
            if s == "int":
                return "integer"
            return s
    # Prefer Date unless time stated/implied — reuse root classifier when available.
    try:
        from app.ai_field_ir import infer_date_or_datetime

        temporal = infer_date_or_datetime(label)
        if temporal:
            return temporal
    except Exception:  # noqa: BLE001
        pass
    if re.search(r"(?i)\b(?:start|end)\s+date\b", label):
        return "date"
    if re.search(r"(?i)\bdatetime\b|\bdate\s*time\b|\btimestamp\b", label):
        return "datetime"
    if re.search(r"(?i)\bdate\b", label):
        return "date"
    return "char"


def _relation_target_display(target: str) -> str:
    raw = (target or "").strip()
    if not raw:
        return raw
    if "." in raw:
        return raw
    parts: list[str] = []
    for w in raw.split():
        if not w:
            continue
        if w.isupper() or (len(w) > 1 and any(c.islower() for c in w[1:])):
            parts.append(w[0].upper() + w[1:] if w[0].islower() else w)
        else:
            parts.append(w.title())
    return " ".join(parts) or raw


def _host_label(host: str | None) -> str | None:
    if not host:
        return None
    try:
        from app.ai_grain import HOST_LABELS

        return HOST_LABELS.get(host, host)
    except Exception:  # noqa: BLE001
        return host


# ---------------------------------------------------------------------------
# parse_det — deterministic floor for ANY grain
# ---------------------------------------------------------------------------


def _parse_det_inherit(text: str, *, host: str | None) -> ConstraintAST:
    ast = ConstraintAST(grain="field_pack", host=host, host_label=_host_label(host), source="det")
    if host:
        # Host row emitted via ast_to_must_do from host/host_label
        pass

    for m in _CHECKBOX_FIELD_RE.finditer(text):
        label = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        if label:
            ast.fields.append(ConstraintField(label=label, ttype="boolean"))

    for m in _TYPED_TEXT_FIELD_RE.finditer(text):
        label = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        label = _LEADING_ARTICLE_RE.sub("", label).strip()
        low = label.lower()
        if not label or low in {"add", "a", "an", "the", "new", "and", "or"}:
            continue
        if low.startswith("checkbox"):
            continue
        ast.fields.append(ConstraintField(label=label, ttype="text"))

    typed_or_check = any(f.ttype in {"boolean", "text"} for f in ast.fields)
    if not typed_or_check:
        for label in iter_add_field_labels(text):
            ttype = _infer_ttype(label)
            bare = bool(re.search(r"(?i)\b(?:start|end)\s+date\b", label)) or ttype in {
                "date",
                "datetime",
            }
            # Match prior Must-do: only start/end date expansions were bare;
            # other Field: rows stay prefixed. Keep bare for start/end date.
            bare = bool(re.search(r"(?i)\b(?:start|end)\s+date\b", label))
            ast.fields.append(ConstraintField(label=label, ttype=ttype, bare=bare))

    gm = _UNDER_GROUP_RE.search(text)
    if gm:
        gtitle = _LEADING_ARTICLE_RE.sub("", gm.group(1).strip()).strip()
        if gtitle:
            ast.hints.append(f"Place under {gtitle} group")

    for m in _STATUS_HINT_RE.finditer(text):
        cond = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        if cond and len(cond) >= 8:
            ast.hints.append(f"Status hint when {cond}")

    if _NO_NEW_APP_RE.search(text):
        if re.search(r"(?i)\binvent\b|\bparallel\b", text):
            host_bit = ""
            if host:
                host_bit = f" {_host_label(host) or host}"
            ast.non_goals.append(f"Do not invent a parallel{host_bit} app")
        else:
            ast.non_goals.append("Do not create a new home-screen app")

    # Honest if thin: mark uncertain so callers prefer extra Must-do over drop
    if host and not ast.fields and not ast.hints:
        ast.uncertain = True
    return ast


def _parse_det_full_app(text: str) -> ConstraintAST:
    ast = ConstraintAST(grain="full_app", source="det")
    # Bare "Do not create a new app" is inherit chrome — not residual Must-do.
    if re.search(r"(?i)\b(?:do\s+not|don't|never)\s+create\b", text) and not (
        _MODEL_WITH_FIELDS_RE.search(text) or re.search(r"(?i)\bname\s*,", text)
    ):
        return ast

    app_m = _APP_NOUN_RE.search(text)
    title = ""
    if app_m:
        title = re.sub(r"\s+", " ", (app_m.group(1) or app_m.group(2) or "")).strip(" .:,-")
        title = re.sub(r"(?i)^(a|an|the)\s+", "", title).strip()
    if not title:
        try:
            from app.ai_document_shape import naming_from_residual

            display, _slug = naming_from_residual(text)
            title = (display or "").strip()
        except Exception:  # noqa: BLE001
            title = ""
    slug = re.sub(r"[^a-z0-9]+", "_", (title or "custom").lower()).strip("_")[:40] or "custom"
    if slug.endswith("_app"):
        slug = slug[: -len("_app")].rstrip("_") or slug
    mid = f"x_{slug}" if not slug.startswith("x_") else slug
    label = title.title() if title else mid
    ast.model_id = mid
    ast.model_label = label

    body = text
    fm = _MODEL_WITH_FIELDS_RE.search(text)
    if fm:
        body = fm.group(1)
    else:
        enum = re.search(
            r"(?i)\b(Name\s*,\s*.+?)(?:\.\s*(?:Simple|No\s+workflow|Menu)|;|$)",
            text,
        )
        if enum:
            body = enum.group(1)

    chunks = split_conjunction_chunks(body)
    # split_conjunction_chunks already handles and/comma; full_app also had
    # simpler and-split — reuse expand path carefully for typed parens.
    for chunk in chunks:
        if not chunk or len(chunk) < 2:
            continue
        sel = re.search(
            r"(?i)^(.+?)\s*\(\s*selection\s*:\s*(.+?)\)\s*(?:\.|$)",
            chunk,
        )
        if sel:
            fname = sel.group(1).strip()
            opts = re.sub(r"\s+", " ", sel.group(2)).strip(" .")
            ast.fields.append(
                ConstraintField(
                    label=fname,
                    ttype="selection",
                    selection_options=opts,
                    bare=True,
                )
            )
            continue
        rel = re.search(
            r"(?i)^(.+?)\s*\(\s*(?:link\s+to\s+)?(.+?)\s*\)\s*$",
            chunk,
        )
        if rel:
            fname = rel.group(1).strip()
            target = rel.group(2).strip()
            target = re.sub(r"(?i)^link\s+to\s+", "", target).strip()
            tlow = target.lower()
            if tlow.startswith("selection"):
                continue
            if tlow in _FIELD_TYPE_HINTS:
                if tlow == "datetime":
                    lab = fname if "datetime" in fname.lower() else f"{fname} datetime"
                    ast.fields.append(
                        ConstraintField(label=lab, ttype="datetime", bare=True)
                    )
                elif tlow == "date":
                    lab = fname if re.search(r"(?i)\bdate\b", fname) else f"{fname} date"
                    ast.fields.append(ConstraintField(label=lab, ttype="date", bare=True))
                elif tlow in {"boolean", "checkbox"}:
                    ast.fields.append(ConstraintField(label=fname, ttype="boolean"))
                else:
                    ast.fields.append(
                        ConstraintField(label=fname, ttype=_infer_ttype(fname, stated=tlow), bare=True)
                    )
                continue
            ast.fields.append(
                ConstraintField(
                    label=fname,
                    ttype="many2one",
                    relation=_relation_target_display(target),
                    bare=True,
                )
            )
            continue
        label_f = re.sub(r"\s+", " ", chunk).strip(" .")
        if label_f.lower() in {"model", "with", "and", "a", "an", "the"}:
            continue
        ast.fields.append(
            ConstraintField(
                label=label_f,
                ttype=_infer_ttype(label_f),
                bare=True,
            )
        )

    mm = _MENU_UNDER_RE.search(text)
    if mm:
        ast.structural.append(f"Menu under {mm.group(1).strip()}")
    if _LIST_FORM_RE.search(text):
        ast.structural.append("List + form")
    if _CREATE_READ_ONLY_RE.search(text):
        ast.structural.append("Create/read only")

    if not ast.fields:
        ast.uncertain = True
    return ast


def parse_det(
    prompt: str,
    *,
    host: str | None = None,
    inherit: bool = False,
    grain: str | None = None,
) -> ConstraintAST:
    """Deterministic floor — always a complete baseline when cues exist.

    ``AI_INTENT_LLM=off`` correctness tests depend only on this path.
    """
    text = (prompt or "").strip()
    if not text:
        return ConstraintAST(uncertain=True, source="det")

    g = (grain or ("field_pack" if inherit else "full_app")).strip() or "full_app"
    if inherit or g in {"field_pack", "feature_slice"}:
        ast = _parse_det_inherit(text, host=host)
        if g == "feature_slice":
            ast.grain = "feature_slice"
        # Prefer inherit also when only inherit flag set without grain
        if not ast.non_goals and inherit and not _NO_NEW_APP_RE.search(text):
            # Match prior: non_goals only when _NO_NEW_APP_RE or explicit invent
            pass
        elif inherit and not ast.non_goals and _NO_NEW_APP_RE.search(text):
            pass  # already set in _parse_det_inherit
        return ast

    if g == "full_app":
        return _parse_det_full_app(text)

    # feature_slice without inherit — still try inherit anchors then full_app
    if host:
        return _parse_det_inherit(text, host=host)
    return _parse_det_full_app(text)


# ---------------------------------------------------------------------------
# parse_llm — optional structured fill (never required for correctness)
# ---------------------------------------------------------------------------

_ALLOWED_TTYPES = frozenset(
    {
        "char",
        "text",
        "html",
        "boolean",
        "integer",
        "float",
        "monetary",
        "binary",
        "image",
        "date",
        "datetime",
        "many2one",
        "many2many",
        "one2many",
        "selection",
    }
)


def parse_llm(payload: Any) -> ConstraintAST | None:
    """Map Flash/constrained JSON → constraint AST. Returns None if unusable."""
    if not isinstance(payload, dict):
        return None
    # Prefer nested constraint_ast; else accept top-level fields/hints/…
    blob = payload.get("constraint_ast")
    if isinstance(blob, dict):
        data = blob
    elif any(k in payload for k in ("fields", "hints", "non_goals", "host", "grain")):
        data = payload
    else:
        return None

    fields_raw = data.get("fields")
    fields: list[ConstraintField] = []
    if isinstance(fields_raw, list):
        for item in fields_raw:
            if isinstance(item, str) and item.strip():
                fields.append(
                    ConstraintField(
                        label=item.strip(),
                        ttype=_infer_ttype(item.strip()),
                        bare=bool(re.search(r"(?i)\b(?:start|end)\s+date\b", item)),
                    )
                )
                continue
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            ttype = str(item.get("ttype") or "char").strip().lower()
            if ttype == "checkbox":
                ttype = "boolean"
            if ttype not in _ALLOWED_TTYPES:
                ttype = _infer_ttype(label)
            rel = item.get("relation")
            relation = str(rel).strip() if rel else None
            opts = item.get("selection_options") or item.get("options")
            sel = str(opts).strip() if opts else None
            bare = bool(item.get("bare")) or ttype in {
                "date",
                "datetime",
                "selection",
                "many2one",
            }
            if ttype == "boolean":
                bare = False
            fields.append(
                ConstraintField(
                    label=label,
                    ttype=ttype,
                    relation=relation,
                    selection_options=sel,
                    bare=bare,
                )
            )

    hints = [
        str(x).strip()
        for x in (data.get("hints") or [])
        if isinstance(data.get("hints"), list) and str(x).strip()
    ]
    non_goals = [
        str(x).strip()
        for x in (data.get("non_goals") or [])
        if isinstance(data.get("non_goals"), list) and str(x).strip()
    ]
    # Also accept out_of_scope-ish keys
    for x in data.get("out_of_scope") or []:
        s = str(x).strip()
        if s and s not in non_goals:
            non_goals.append(s)

    host = data.get("host") or data.get("host_model")
    host_s = str(host).strip() if host else None
    grain = str(data.get("grain") or "").strip() or "full_app"
    model_id = data.get("model_id")
    model_label = data.get("model_label")
    structural = [
        str(x).strip()
        for x in (data.get("structural") or [])
        if isinstance(data.get("structural"), list) and str(x).strip()
    ]

    # Thin LLM fill without fields/hints → uncertain (prefer extra over drop)
    uncertain = not fields and not hints and not structural
    if not fields and not hints and not non_goals and not host_s and not structural:
        return None

    return ConstraintAST(
        grain=grain,
        host=host_s,
        host_label=_host_label(host_s) if host_s else None,
        fields=fields,
        hints=hints,
        non_goals=non_goals,
        model_id=str(model_id).strip() if model_id else None,
        model_label=str(model_label).strip() if model_label else None,
        structural=structural,
        uncertain=uncertain,
        source="llm",
    )


# ---------------------------------------------------------------------------
# ast_to_must_do — AST → operator-facing bullets (stable formats for IR)
# ---------------------------------------------------------------------------


def ast_to_must_do(ast: ConstraintAST, *, cap: int = _MUST_DO_CAP) -> list[str]:
    """Render constraint AST as Diagnosis Must-do bullets."""
    rows: list[str] = []
    if ast.host and (ast.grain in {"field_pack", "feature_slice"} or ast.host_label):
        label = ast.host_label or _host_label(ast.host) or ast.host
        rows.append(f"On {label} ({ast.host})")

    if ast.model_id:
        mid = ast.model_id
        mlabel = ast.model_label or mid
        rows.append(f"New model {mid} ({mlabel})")

    for f in ast.fields:
        if f.ttype == "boolean":
            rows.append(f"Checkbox: {f.label}")
        elif f.ttype == "text":
            rows.append(f"Text field: {f.label}")
        elif f.ttype == "selection" and f.selection_options:
            rows.append(f"{f.label} selection ({f.selection_options})")
        elif f.ttype == "many2one" and f.relation:
            rows.append(f"{f.label}→{f.relation}")
        elif f.bare or re.search(r"(?i)\b(?:start|end)\s+date\b", f.label):
            rows.append(f.label)
        else:
            rows.append(f"Field: {f.label}")

    rows.extend(ast.hints)
    rows.extend(ast.structural)
    rows.extend(ast.non_goals)

    # Honest if uncertain: keep extras; never silently empty when host known
    out = _dedupe_strs(rows)
    if ast.uncertain and not out and ast.host:
        label = ast.host_label or _host_label(ast.host) or ast.host
        out = [f"On {label} ({ast.host})"]
    return out[:cap]


# ---------------------------------------------------------------------------
# merge — never shrink below det floor
# ---------------------------------------------------------------------------


def merge_asts(det: ConstraintAST, llm: ConstraintAST | None) -> ConstraintAST:
    """Union LLM fill onto det floor. Det host/grain/fields always survive."""
    if llm is None:
        return det

    # Fields: det first, then llm by novel label
    seen = {_norm_label(f.label) for f in det.fields}
    fields = list(det.fields)
    for f in llm.fields:
        key = _norm_label(f.label)
        if not key or key in seen:
            continue
        # Also skip if det already has a start/end expansion covering base
        seen.add(key)
        fields.append(f)

    hints = _dedupe_strs(list(det.hints) + list(llm.hints))
    non_goals = _dedupe_strs(list(det.non_goals) + list(llm.non_goals))
    structural = _dedupe_strs(list(det.structural) + list(llm.structural))

    host = det.host or llm.host
    host_label = det.host_label or llm.host_label or _host_label(host)
    grain = det.grain or llm.grain
    model_id = det.model_id or llm.model_id
    model_label = det.model_label or llm.model_label

    return ConstraintAST(
        grain=grain,
        host=host,
        host_label=host_label,
        fields=fields,
        hints=hints,
        non_goals=non_goals,
        model_id=model_id,
        model_label=model_label,
        structural=structural,
        uncertain=bool(det.uncertain and llm.uncertain),
        source="mixed",
    )


def _row_covered(row: str, joined_lower: str) -> bool:
    key = row.lower()
    if key in joined_lower:
        return True
    toks = [t for t in re.split(r"\W+", key) if len(t) >= 4]
    if toks and all(t in joined_lower for t in toks[:3]):
        return True
    return False


def merge_must_do(
    det_rows: list[str],
    llm_rows: list[str],
    *,
    cap: int = _MUST_DO_CAP,
) -> list[str]:
    """Union LLM Must-do with deterministic floor — never drop det seed bullets.

    When over ``cap``, det floor wins; LLM extras fill remaining slots.
    """
    det = _dedupe_strs([str(x).strip() for x in det_rows if str(x).strip()])
    llm = _dedupe_strs([str(x).strip() for x in llm_rows if str(x).strip()])
    if not llm:
        return det[:cap]
    if not det:
        return llm[:cap]

    # Floor first — never truncated away
    floor = list(det)
    if len(floor) >= cap:
        return floor[:cap]

    joined = " | ".join(floor).lower()
    extras: list[str] = []
    for row in llm:
        if _row_covered(row, joined):
            continue
        # Skip redundant host-only LLM lines when floor already hosts
        key = row.lower()
        if key.startswith("on ") and any(
            bit in joined for bit in ("on ", "sale.order", "res.partner", "purchase.order")
        ):
            # Still add if tokens not covered
            toks = [t for t in re.split(r"\W+", key) if len(t) >= 4]
            if toks and all(t in joined for t in toks[:2]):
                continue
        extras.append(row)
        joined = " | ".join(floor + extras).lower()

    room = cap - len(floor)
    return _dedupe_strs(floor + extras[:room])


# Schema fragment for Flash enrich (optional; never required for tests)
CONSTRAINT_AST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "ttype": {"type": "string"},
                    "relation": {"type": "string"},
                },
                "required": ["label"],
            },
        },
        "host": {"type": "string"},
        "hints": {"type": "array", "items": {"type": "string"}},
        "non_goals": {"type": "array", "items": {"type": "string"}},
        "grain": {"type": "string"},
        "model_id": {"type": "string"},
        "model_label": {"type": "string"},
        "structural": {"type": "array", "items": {"type": "string"}},
    },
}


__all__ = [
    "CONSTRAINT_AST_SCHEMA",
    "ConstraintAST",
    "ConstraintField",
    "ast_to_must_do",
    "expand_field_chunk",
    "iter_add_field_labels",
    "merge_asts",
    "merge_must_do",
    "parse_det",
    "parse_llm",
    "split_conjunction_chunks",
]

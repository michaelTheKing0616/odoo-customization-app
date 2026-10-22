"""Source-anchored intent contracts for App Studio decisions.

The contract is a verification boundary, not a second design engine. Models
propose; deterministic code decides which delivery lane a requirement may use:

  metadata -> stock_automation -> option_a (custom Python)

A requirement is either *stated* (its quote resolves to a positive span of the
operator's brief) or *inferred* (the model filled a gap the operator left).
Inferred requirements may enrich the design as metadata, but they can never
reach a code lane without the operator's explicit answer.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.text_negation import span_is_negated

_KINDS = frozenset(
    {"app_name", "field", "host", "integration", "model", "python", "automation", "other"}
)
_DECISIONS = frozenset({"metadata", "stock_automation", "option_a", "clarify", "declined"})
_CODE_LANES = frozenset({"stock_automation", "option_a"})
_ORIGINS = frozenset({"stated", "inferred"})
_PROVENANCE = frozenset({"quoted", "derived", "suggested"})
_CONFIDENCE = frozenset({"low", "medium", "high"})
_MAX_REQUIREMENTS = 32
_AUTOMATIC_TRIGGERS = frozenset({"event", "time", "computation", "external"})
_ENTERED_TRIGGERS = frozenset({"none", "user_entry"})
# Every lane above metadata must have ruled out every rung below it.
_LADDER = {"stock_automation": ("metadata",), "option_a": ("metadata", "stock_automation")}


def _text(value: Any, limit: int = 240) -> str:
    if isinstance(value, (dict, list)):
        return ""
    return str(value or "").strip()[:limit]


def _sentence(value: Any, limit: int = 320) -> str:
    """Whole sentences only: never cut a question mid-sentence."""
    text = re.sub(r"\s+", " ", _text(value, 4000))
    if len(text) <= limit:
        return text
    cut = max(text.rfind(m, 0, limit + 1) for m in (". ", "? ", "! "))
    return text[: cut + 1].strip() if cut > 0 else ""


# Hosting limits (Odoo Online cannot install custom Python) are decided in code:
# Python pieces go to the custom-code path and everything else is built as data.
# A model question about that known constraint is not a real ambiguity.
_PLATFORM_RE = re.compile(
    r"(?i)\b(odoo\s*online|odoo\.sh|saas|hosting|hosted|self-?hosted|on-?prem)\b.*"
    r"\b(python|\.py|custom (code|module)s?|modules?)\b|"
    r"\b(python|\.py|custom (code|module)s?)\b.*\b(odoo\s*online|hosting|hosted|saas)\b"
)


# Platform / integration concerns the code already decides (brief_integrations defers
# missing apps, modules declare dependencies, records respect company rules).
_RESOLVED_BY_CODE_RE = re.compile(
    r"(?i)(graceful\w*|fallback|fail\w* (gracefully|safely)|"
    r"(not|non)[- ]?install\w*|missing (app|module)s?|optional (odoo )?(app|module|integration)s?|"
    r"(install|uninstall)\w*.{0,30}(clean\w*|safe\w*|without (errors?|breaking))|"
    r"clean (install|uninstall)|dependenc(y|ies)|depends on|manifest|"
    r"multi[- ]?compan\w*|company rules?|record rules? per company|"
    r"(who|only \w+) (can|should|may) (cancel|delete|see|view)|(can|should|may)(n'?t| not)? (cancel|see|view)\b|"
    r"cancel(lation)? (rights?|permissions?)|visibility|access (rights?|control))"
)


_TECH_WORDS = re.compile(r"(?i)\b(x_\w+|ir\.\w+|res\.\w+|base\.automation|model|field|python|module|many2one|selection)\b")


def _answer_options(raw: Any) -> list[dict[str, str]]:
    """AI-proposed answers: 2-4, non-empty, distinct, short, plain; each mapped to a build way."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        label = _text(item.get("label") if isinstance(item, dict) else item, 80)
        decision = _text(item.get("decision"), 24).lower() if isinstance(item, dict) else ""
        key = label.casefold()
        if not label or len(label) > 70 or key in seen or _TECH_WORDS.search(label):
            continue
        seen.add(key)
        opt = {"label": label, "decision": decision if decision in {"metadata", "stock_automation", "option_a"} else "metadata"}
        if isinstance(item, dict) and item.get("recommended") is True:
            opt["recommended"] = True
        out.append(opt)
    return out[:4] if len(out) >= 2 else []


_MANUAL_CUE = re.compile(
    r"(?i)\b(manual\w*|by hand|(staff|users?|people|managers?|they|team) (enter|type|fill|update|set|record)s?\b|"
    r"entered by|typed (in|by)|not automatic\w*)"
)

_AUTO_CUE = re.compile(
    r"(?i)\b(alerts?|notif\w*|remind\w*|warn\w*|automatic\w*|automated|escalat\w*|"
    r"schedule (a|an)\b[^.]{0,40}\bactivit\w*|daily|every (day|week|month)|when [^.]{3,80}\b(then|set|create|schedule|notify|move)"
    r"|\b(if|when|whenever|once)\b[^.]{3,120}\b(should|must|will)?\s*(get|receive|be given)\b[^.]{0,30}\b(to-?do|task|activit\w*|call))"
)


def _brief_says_automatic(row: dict[str, Any]) -> bool:
    """A build-way question about something the brief explicitly makes automatic."""
    if row.get("decision") != "clarify" or row.get("origin") != "stated":
        return False
    if row.get("options") or str(row.get("downgrade_reason") or "").startswith(_CONFLICT_PREFIX):
        return False  # a real business question, or a contradiction the operator must settle
    if row.get("kind") in {"python", "host"}:
        return False  # custom code always needs the operator's say
    q = str(row.get("question") or "")
    if q and not _BUILD_Q.search(q):
        return False
    ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    return bool(_AUTO_CUE.search(f"{ev.get('quote') or ''} {row.get('subject') or ''}"))


_BUILD_Q = re.compile(r"(?i)\b(enter|entered|type|fill|automatic\w*|by itself|computed?|calculated?)\b")


def is_platform_constraint_question(row: dict[str, Any]) -> bool:
    if row.get("decision") != "clarify":
        return False
    blob = " ".join(
        str(row.get(k) or "") for k in ("subject", "question", "why_metadata_cannot_do_it", "mechanism")
    )
    if row.get("kind") in {"host", "python", "other", "model"} and _PLATFORM_RE.search(blob):
        return True
    # Subject-level match only: a real feature that merely mentions a module stays.
    if _RESOLVED_BY_CODE_RE.search(str(row.get("subject") or "")) or re.search(
        r"(?i)\b(who|only \w+) (can|should|may|is allowed to) (cancel|delete|see|view)\b|"
        r"\b(non-?managers?|managers?|supervisors?|front desk|staff)\b[^?]{0,60}\b(cancel|see|view|hide)\b|"
        r"\b(cancel|see|view|hide)\b[^?]{0,60}\b(non-?managers?|managers?|front desk)\b", str(row.get("question") or "")
    ):
        return True
    # A question that only exists because an app is not installed: the integration
    # plan already defers those links (built here, linked once the app is installed).
    return bool(_MISSING_APP_Q_RE.search(str(row.get("question") or "")))


_MISSING_APP_Q_RE = re.compile(
    r"(?i)\b(is|are)\s+(currently\s+)?not\s+installed\b|\bisn'?t\s+installed\b|"
    r"\buntil\s+\w+(\s+\w+)?\s+is\s+installed\b|\bnot\s+in(stalled)?\s+(in\s+)?(your|this)\s+database\b"
)


def _identifier(value: Any, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", _text(value, 80).lower()).strip("_")
    return (text or fallback)[:48]


def _evidence_quote(value: Any) -> Any:
    """Accept either an LLM quote string or an already-normalized evidence row."""
    return value.get("quote") if isinstance(value, dict) else value


def locate_evidence(prompt: str, quote: Any) -> dict[str, Any] | None:
    """Resolve a model-provided quote to a positive, inspectable prompt span."""
    brief = prompt or ""
    needle = _text(quote, 300)
    if len(needle) < 6 or not brief:
        return None
    start = brief.find(needle)
    end = start + len(needle) if start >= 0 else -1
    if start < 0:
        start = brief.casefold().find(needle.casefold())
        end = start + len(needle) if start >= 0 else -1
    if start < 0:
        words = re.findall(r"\S+", needle)
        if not words:
            return None
        match = re.search(r"\s+".join(re.escape(word) for word in words), brief, re.I)
        if match is None:
            match = _loose_match(brief, needle)
        if match is None:
            return None
        start, end = match if isinstance(match, tuple) else match.span()
    if span_is_negated(brief, start):
        return None
    return {"quote": brief[start:end], "start": start, "end": end}


_MARKUP = re.compile(r"[*_`#>\u201c\u201d\u2018\u2019\"'\u2013\u2014-]+")


def _loose_match(brief: str, needle: str) -> tuple[int, int] | None:
    """Match a quote ignoring markdown, bullets, quote marks and dashes."""
    words = [w for w in _MARKUP.sub(" ", needle).split() if w]
    if len(words) < 2:
        return None
    gap = r"[\s*_`#>\u201c\u201d\u2018\u2019\"'\u2013\u2014-]+"
    m = re.search(gap.join(re.escape(w) for w in words), brief, re.I)
    return m.span() if m else None


def subject_in_brief(prompt: str, subject: str) -> dict[str, Any] | None:
    """A heading or line that names the subject's key words (e.g. '## 10. Automated Alerts')."""
    plain = re.sub(r"\b[a-z]+\.([a-z_.]+)", lambda m: m.group(1).replace("_", " ").replace(".", " "), (subject or "").lower())
    keys = {w.rstrip("s") for w in re.findall(r"[a-z]{4,}|\d{2,}", plain)} - {
        "field", "view", "partner", "contact",
        "customer", "proactive", "automated", "custom", "with", "from", "that", "integration",
        "management", "system", "configuration", "setting", "module", "feature", "report", "tracking",
        "odoo", "health", "score", "data", "record"}
    if not keys or not prompt:
        return None
    pos, best, best_n = 0, None, 0
    for line in prompt.splitlines(keepends=True):
        words = {w.rstrip("s") for w in re.findall(r"[a-z]{4,}|\d{2,}", line.lower())}
        hit = keys & words
        n = len(hit) * 100 + sum(len(w) for w in hit)  # more shared words, then longer ones
        if line.lstrip().startswith("#") and hit and (2 * len(hit) >= len(keys) or max(map(len, hit)) >= 5) and n > best_n and not span_is_negated(prompt, pos):
            text = line.strip()
            start = prompt.find(text, pos)
            best, best_n = {"quote": text, "start": start, "end": start + len(text), "from_heading": True}, n
        pos += len(line)
    if best is not None:
        return best
    return _sentence_match(prompt, subject)


_STOP = frozenset(
    "the and for with from that this when where into onto than then them they their there have "
    "has had will would should could must shall also each other such about over under only "
    "case cases make made create allow able using used via like".split()
)


def _stems(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z]{3,}", (text or "").lower()):
        if w in _STOP:
            continue
        for suf in ("fully", "ingly", "ation", "ment", "ness", "ing", "ful", "ed", "ly", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 4:
                w = w[: -len(suf)]
                break
        out.add(w[:6])
    return out


_DUTY_SUBJ = re.compile(r"(?i)remind|alert|notif|warn|activit|follow.?up|escalat|schedul|due")
_DUTY_SENT = re.compile(r"(?i)\b(forget|forgot|every\s+(few|couple of|\d+|other)?\s*(days?|weeks?|months?|years?)|"
                        r"remind\w*|overdue)\b"
                        # a direct duty with its condition: "alert doctor if result abnormal"
                        r"|\b(alert|notify|tell|inform|warn|remind|to-?do|follow.?up)\w*\b[^.!?]*\b(if|when|whenever|once)\b"
                        r"|\b(if|when|whenever|once)\b[^.!?]*\b(alert|notify|tell|inform|warn|remind|to-?do|follow.?up)\w*")


def duty_match(prompt: str, subject: str) -> dict[str, Any] | None:
    """Source-anchored match for a reminder-style step: the brief names the thing (e.g. 'servicing')
    in a sentence that also states the duty ('every few months', 'we always forget')."""
    if not _DUTY_SUBJ.search(subject or ""):
        return None
    keys = _stems(subject) - {"remind", "alert", "notif", "warn", "activit", "schedu", "due", "equipm",
                              "custom", "odoo", "record", "automa"}
    for m in re.finditer(r"[^.!?\n]+[.!?]?", prompt or ""):
        sent = m.group(0)
        hit = {k for k in keys & _stems(sent) if len(k) >= 5}
        if hit and _DUTY_SENT.search(sent) and not span_is_negated(prompt, m.start()):
            text = sent.strip()
            start = prompt.find(text, m.start())
            return {"quote": text, "start": start, "end": start + len(text)}
    return None


_AUTO_OPT = re.compile(r"(?i)automatic|by itself|system|odoo does|auto\b|server action|scheduled")
_MANUAL_OPT = re.compile(r"(?i)manual|by hand|people|staff|user|confirm|enter|type|hand-?off")


def resolve_way_question(row: dict[str, Any], prompt: str) -> dict[str, Any] | None:
    """An AI question whose only answers are 'automatic' vs 'manual' is a build-way choice code can
    settle: automatic when the brief's own words imply it, else manual. Recorded as an assumption."""
    opts = row.get("options") or []
    if row.get("decision") != "clarify" or len(opts) != 2 or row.get("kind") in {"python", "host"}:
        return None
    auto = [o for o in opts if _AUTO_OPT.search(o["label"]) and not _MANUAL_OPT.search(o["label"])]
    manual = [o for o in opts if _MANUAL_OPT.search(o["label"]) and not _AUTO_OPT.search(o["label"])]
    if len(auto) != 1 or len(manual) != 1:
        return None
    ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    anchor = f"{ev.get('quote') or ''} {(duty_match(prompt, row.get('subject', '')) or {}).get('quote', '')}"
    if _AUTO_CUE.search(anchor) or re.search(r"(?i)\bwhen\b[^.]{3,80}\b(set|create|move|update|schedul)", anchor):
        return dict(row, decision="stock_automation", verified=True, options=[], question="",
                    alternatives=[manual[0]["label"]],
                    assumption=f"Assumed '{auto[0]['label']}': your brief describes this happening on its own.",
                    downgrade_reason=f"Assumed '{auto[0]['label']}': your brief describes this happening on its own.")
    return dict(row, decision="metadata", options=[], question="", alternatives=[auto[0]["label"]],
                assumption=f"Assumed '{manual[0]['label']}': your brief does not ask for this to be automatic.",
                downgrade_reason=f"Assumed '{manual[0]['label']}': your brief does not ask for this to be automatic.")


_UNSAFE_OPT = re.compile(r"(?i)\b(delet\w*|remov\w*|archiv\w*|overwrit\w*|wipe|purge|irreversib\w*|permanent\w*|refund\w*|charg\w*|pay\w*|send to (all )?customers?|email (all )?customers?)\b")
MAX_BLOCKING = 3


def default_answer(row: dict[str, Any], prompt: str, *, settle_build_way: bool = False) -> dict[str, Any] | None:
    """Code settles an AI question when it safely can: the option the brief's own words back
    (source-anchored), else the AI's recommended option. Returns the row with an editable
    assumption, or None when no option is safe to default."""
    opts = row.get("options") or []
    if row.get("decision") != "clarify" or row.get("kind") in {"python", "host"}:
        return None
    if str(row.get("downgrade_reason") or "").startswith(_CONFLICT_PREFIX):
        return None  # a real contradiction is the operator's call
    if len(opts) < 2:
        if not settle_build_way or row.get("origin") == "inferred" or row.get("operator_confirmed"):
            return None  # an App Studio suggestion or a held code lane stays the operator's call
        if not (row.get("automation") and row.get("target_model")) and row.get("kind") not in {"field", "automation", "other"}:
            return None
        # No answers offered: it is a build-way choice. Automatic only when the brief's own words
        # say so and a no-code automation is fully specified; otherwise people enter it.
        ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        anchor = f"{ev.get('quote') or ''} {(duty_match(prompt, row.get('subject', '')) or {}).get('quote', '')}"
        auto = bool(_AUTO_CUE.search(anchor) or re.search(r"(?i)\bwhen\b[^.]{3,80}\b(set|create|move|update|schedul)", anchor))
        if auto and row.get("automation") and row.get("target_model"):
            note = "Assumed Odoo does this automatically, because your brief describes it happening on its own."
            return dict(row, decision="stock_automation", verified=True, question="", options=[],
                        assumption=note, downgrade_reason=note[:160], alternatives=["People do it by hand"])
        note = ("Assumed people do this by hand for now" + (
            " (App Studio could not set up the automatic version safely)" if auto else "") + ".")
        return dict(row, decision="metadata", question="", options=[], assumption=note,
                    downgrade_reason=note[:160], alternatives=["Odoo does it automatically"] if auto else [])
    ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    topic = _stems(f"{row.get('subject') or ''} {row.get('question') or ''} {ev.get('quote') or ''}")
    generic = {"should", "would", "which", "person", "user", "record", "option", "system"}
    sents = [m.group(0) for m in re.finditer(r"[^.!?\n]+[.!?]?", prompt or "")
             if len((topic - generic) & _stems(m.group(0))) >= 2 and not span_is_negated(prompt, m.start())]
    best, best_n, tie, anchor = None, 0, False, ""
    for o in opts:
        st = _stems(o["label"]) - generic
        for sent in sents:
            n = len(st & _stems(sent))
            if n > best_n:
                best, best_n, tie, anchor = o, n, False, sent.strip()
            elif n == best_n and n and best is not o:
                tie = True
    if best is not None and not tie and not _UNSAFE_OPT.search(best["label"]):
        why = f"your brief says \u201c{anchor[:120]}\u201d"
    else:
        best = next((o for o in opts if o.get("recommended")), None)
        why = "the usual safe choice"
        if best is None or _UNSAFE_OPT.search(best["label"]):
            return None
    choice = best["decision"] if best["decision"] in {"metadata", "stock_automation"} else None
    if choice is None:
        return None  # custom code still needs the operator's OK
    note = f"Assumed '{best['label']}' because {why}. To change it, say so in a refine."
    return dict(row, decision=choice, options=[], question="", assumption=note, downgrade_reason=note[:160],
                assumed_option=best["label"], alternatives=[o["label"] for o in opts if o is not best])


def settle_open_questions(requirements: list[dict[str, Any]], prompt: str) -> list[dict[str, Any]]:
    """Last deterministic pass after the verifier and conflict checks: every open question the
    brief or a safe default can answer becomes an editable assumption; at most MAX_BLOCKING stay."""
    out = []
    for r in requirements:
        if r.get("decision") == "clarify" and not r.get("operator_confirmed"):
            r = resolve_way_question(r, prompt) or default_answer(r, prompt, settle_build_way=True) or r
        out.append(r)
    blocking = [r for r in out if r.get("decision") == "clarify" and not r.get("operator_confirmed")]
    for r in blocking[MAX_BLOCKING:]:
        r.update(decision="declined", assumption="Left out for now; ask for it in a refine to add it.",
                 downgrade_reason="Left out for now; ask for it in a refine to add it.")
    return out


def _sentence_match(prompt: str, subject: str) -> dict[str, Any] | None:
    """Paraphrase match: a brief sentence sharing most of the subject's content words."""
    # App names appear all over a brief; they cannot prove a paraphrase on their own.
    keys = _stems(subject) - {"custom", "odoo", "app", "system", "featur", "integr", "non", "crm", "sale",
                              "sales", "helpde", "invoic", "projec", "contac", "subscr", "calend",
                              "accoun", "invent", "purcha", "employ"}
    if len(keys) < 2:
        return None
    best, best_n = None, 0
    for m in re.finditer(r"[^.!?\n]+[.!?]?", prompt or ""):
        hit = keys & _stems(m.group(0))
        if len(hit) >= 2 and 3 * len(hit) >= len(keys) and len(hit) > best_n:
            if span_is_negated(prompt, m.start()):
                continue
            text = m.group(0).strip()
            start = prompt.find(text, m.start())
            best, best_n = {"quote": text, "start": start, "end": start + len(text), "from_heading": True}, len(hit)
    return best


def _rungs(raw: Any) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in raw if isinstance(raw, list) else []:
        if not isinstance(r, dict):
            continue
        rung = _text(r.get("rung"), 24).lower()
        if rung in {"metadata", "stock_automation"}:
            out[rung] = {
                "rung": rung,
                "mechanism": _text(r.get("mechanism"), 120),
                "sufficient": r.get("sufficient") is True,
                "why": _text(r.get("why"), 200),
            }
    return list(out.values())


_WHEN = frozenset({"on_create", "on_write", "on_time", "untouched"})
# activity: schedule a to-do; set_fields: write fixed values; notify: to-do for the responsible person
# (or a named group's members) when a condition holds.
_ACTIONS = frozenset({"activity", "set_fields", "notify"})
_DOMAIN_OPS = frozenset({"=", "!=", "<", ">", "<=", ">=", "in", "not in"})
_IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _literal(v: Any) -> Any:
    """Plain values only (no expressions): text, number, true/false, or a short list of those."""
    if isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return v[:80]
    if isinstance(v, list) and all(isinstance(x, (str, int, float)) for x in v):
        return v[:10]
    return None


def _domain(raw: Any) -> list[list[Any]]:
    out = []
    for t in raw if isinstance(raw, list) else []:
        if (isinstance(t, list) and len(t) == 3 and isinstance(t[0], str) and _IDENT.match(t[0])
                and t[1] in _DOMAIN_OPS and _literal(t[2]) is not None):
            out.append([t[0], t[1], _literal(t[2])])
    return out[:5]


def _automation_spec(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    when = _text(raw.get("when"), 12).lower()
    action = _text(raw.get("action"), 12).lower()
    if when not in _WHEN or action not in _ACTIONS:
        return {}
    try:
        offset = int(raw.get("offset_days") or 0)
    except (TypeError, ValueError):
        offset = 0
    raw_values = raw.get("values") if isinstance(raw.get("values"), dict) else {}
    values = {k: _literal(v) for k, v in raw_values.items()
              if isinstance(k, str) and _IDENT.match(k) and _literal(v) is not None}
    if (action == "set_fields" and not values) or (when == "untouched" and offset <= 0):
        return {}
    spec: dict[str, Any] = {
        "when": when,
        "action": action,
        "date_field": _identifier(raw.get("date_field"), ""),
        "offset_days": max(-3650, min(3650, offset)),
        "summary": _text(raw.get("summary"), 120),
    }
    if values:
        spec["values"] = dict(list(values.items())[:6])
    if _domain(raw.get("condition")):
        spec["condition"] = _domain(raw.get("condition"))
    if action == "notify" and _text(raw.get("group"), 80):
        spec["group"] = _text(raw.get("group"), 80)
    return spec


def ladder_is_complete(decision: str, rungs: list[dict[str, Any]]) -> bool:
    """True when every lower rung was considered and ruled out with a reason."""
    by = {r["rung"]: r for r in rungs}
    return all(
        k in by and not by[k]["sufficient"] and len(by[k]["why"]) >= 8
        for k in _LADDER.get(decision, ())
    )


def _gate_lane(
    decision: str, trigger: str, rungs: list[dict[str, Any]], target: str
) -> tuple[str, str]:
    """Deterministic policy over structure, never keywords."""
    if decision not in _CODE_LANES:
        return decision, ""
    if trigger in _ENTERED_TRIGGERS:
        return "metadata", "The brief describes entered data, not automatic behavior."
    if trigger not in _AUTOMATIC_TRIGGERS or not ladder_is_complete(decision, rungs):
        return "clarify", "A code lane was proposed without a complete built-in apps first justification."
    if decision == "stock_automation" and not target:
        return "clarify", "An automation was proposed without a target model."
    return decision, ""


REQUIREMENT_ROLES = frozenset({"record", "attribute", "dimension", "context", "future", "rule", "access"})


def normalize_intent_contract(
    raw: Any, prompt: str, *, trusted: bool = False, clause_mode: bool = False
) -> list[dict[str, Any]]:
    """Keep bounded, well-formed decisions.

    ``trusted`` is only for rows this process already produced (stored session
    contract, validate_and_repair). It is the only way ``verified``,
    ``operator_confirmed`` and ``declined`` are honored; model output can never
    set them.
    """
    entries = raw.get("requirements") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in entries[:_MAX_REQUIREMENTS]:
        if not isinstance(item, dict):
            continue
        kind = _text(item.get("kind"), 24).lower()
        decision = _text(item.get("decision") or item.get("delivery"), 24).lower()
        subject = _text(item.get("subject") or item.get("label") or item.get("name"), 100)
        if kind not in _KINDS or decision not in _DECISIONS or not subject:
            continue
        if decision == "declined" and not trusted:
            # Only the operator declines; a model "declined" becomes a question.
            decision = "clarify"
        origin = _text(item.get("origin"), 12).lower()
        origin = origin if origin in _ORIGINS else "stated"
        evidence = locate_evidence(
            prompt, _evidence_quote(item.get("evidence")) or item.get("quote")
        )
        ev_raw = item.get("evidence")
        if evidence is None and trusted and not prompt and isinstance(ev_raw, dict):
            quote = _text(ev_raw.get("quote"), 300)
            if quote:  # operator-edit path has no brief; the span was verified earlier
                start = ev_raw.get("start") if isinstance(ev_raw.get("start"), int) else 0
                end = ev_raw.get("end") if isinstance(ev_raw.get("end"), int) else 0
                evidence = {"quote": quote, "start": start, "end": end}
        duty_anchor = False
        if not trusted and not clause_mode and (evidence is None or origin == "inferred"):
            # The brief names it in a section heading: stated, not an App Studio suggestion.
            heading = subject_in_brief(prompt, subject)
            if heading is None:
                heading = duty_match(prompt, subject)
                duty_anchor = heading is not None
            if heading is not None:
                evidence = evidence or heading
                origin = "stated"
        if evidence is None:
            # A quote that does not resolve is demoted to an inference, not trusted.
            evidence = {"quote": "", "start": 0, "end": 0}
            origin = "inferred"
        # One provenance enum across layers: stated -> quoted, inferred -> suggested.
        # In clause mode code (clause_grounding.ground_items) set it; the model never can.
        prov = _text(item.get("provenance"), 12).lower() if (trusted or clause_mode) else ""
        if prov not in _PROVENANCE:
            prov = "quoted" if origin == "stated" else "suggested"
        if prov != "quoted":
            origin = "inferred"
        elif origin == "inferred":
            prov = "suggested"
        identity = f"{kind}\n{subject.casefold()}\n{evidence['quote'].casefold()}"
        requirement_id = f"requirement_{hashlib.sha256(identity.encode()).hexdigest()[:12]}"
        if requirement_id in seen:
            continue
        trigger = _text(item.get("trigger"), 16).lower()
        rungs = _rungs(item.get("rungs"))
        target = _text(item.get("target_model"), 60).lower()
        suggested_lane = ""
        confirmed = trusted and item.get("operator_confirmed") is True
        verified = trusted and item.get("verified") is True
        note = _text(item.get("downgrade_reason"), 160) if trusted else ""
        if decision in _CODE_LANES and not confirmed:
            if origin == "inferred" and clause_mode:
                # Visible suggestion, never a code lane and never a blocking question.
                suggested_lane, decision = decision, "metadata"
                note = "Suggested: your brief does not clearly ask for this to happen on its own."
            elif origin == "inferred":
                decision = "clarify"
                note = "This was not in your brief, so it is not built without your OK."
            else:
                proposed = decision
                decision, gate_note = _gate_lane(decision, trigger, rungs, target)
                note = gate_note or note
                if (duty_anchor and proposed == "stock_automation" and decision == "clarify" and target
                        and trigger in _AUTOMATIC_TRIGGERS):
                    # The brief itself names this duty; a built-in automation (no code) is authorized.
                    decision, note = "stock_automation", "Your brief asks for this to happen automatically."
                if decision in _CODE_LANES and trusted and not verified:
                    decision, note = "clarify", "The code lane was not independently verified."
        reason = _text(item.get("why_metadata_cannot_do_it") or item.get("reason"), 240) or " ".join(
            r["why"] for r in rungs
        )[:240]
        alternative = _text(item.get("metadata_alternative") or item.get("alternative"), 180) or next(
            (r["mechanism"] for r in rungs if r["rung"] == "metadata"), ""
        )
        confidence = _text(item.get("confidence"), 12).lower()
        row_out = {
                "id": requirement_id,
                "kind": kind,
                "subject": subject,
                "decision": decision,
                "origin": origin,
                "evidence": evidence,
                "trigger": trigger,
                "target_model": target,
                "mechanism": _text(item.get("mechanism"), 120),
                "automation": _automation_spec(item.get("automation")),
                "rungs": rungs,
                "why_metadata_cannot_do_it": reason,
                "metadata_alternative": alternative,
                "question": _sentence(item.get("question")),
                "options": _answer_options(item.get("options")),
                "confidence": confidence if confidence in _CONFIDENCE else "medium",
                # Fix plan (a): entity-vs-attribute role, one enum on the existing call; "" when absent.
                "role": (lambda r: r if r in REQUIREMENT_ROLES else "")(_text(item.get("role"), 16).lower()),
                "verified": verified,
                "operator_confirmed": confirmed,
                "downgrade_reason": note,
                "assumption": _text(item.get("assumption"), 240) if trusted else "",
                "alternatives": [_text(a, 80) for a in (item.get("alternatives") or [])[:4]] if trusted else [],
                "operator_choice": _text(item.get("operator_choice"), 160) if trusted else "",
                "provenance": prov,
            }
        if suggested_lane:
            row_out.update(suggested_lane=suggested_lane, question="", options=[])
        if trusted or clause_mode:
            for key, lim in (("relation", 16), ("rule_id", 40), ("entailment", 12), ("grounding_problem", 160)):
                if item.get(key):
                    row_out[key] = _text(item.get(key), lim)
            if isinstance(item.get("clause_ids"), list):
                row_out["clause_ids"] = [_text(i, 8) for i in item["clause_ids"][:3]]
            if isinstance(item.get("stock_check"), list):
                row_out["stock_check"] = item["stock_check"][:4]
            if item.get("suggested_lane") in _CODE_LANES:
                row_out["suggested_lane"] = item["suggested_lane"]
            if item.get("needs_review") is True:
                row_out["needs_review"] = True
        seen.add(requirement_id)
        # Only the model's own build-way question; a code-lane row code held back stays the operator's call.
        if str(item.get("decision") or "").strip().lower() == "clarify" and _brief_says_automatic(row_out):
            # The brief itself asks for this to happen automatically: decided, not asked.
            row_out.update(decision="stock_automation", verified=True,
                           downgrade_reason="Your brief asks for this to happen automatically.")
        settled = (resolve_way_question(row_out, prompt) or default_answer(row_out, prompt)) if not trusted else None
        if settled is not None:
            row_out = settled
        if is_platform_constraint_question(row_out):
            continue  # resolved deterministically; the diagnosis shows the custom-code note
        if (row_out["decision"] in _CODE_LANES and row_out.get("provenance") != "quoted"
                and not row_out.get("operator_confirmed")):
            # Provenance gate: only quoted rows may hold a code lane without the operator's OK.
            if clause_mode or row_out.get("provenance") == "derived":
                # A visible suggestion, not a blocking question (blocking a run costs more than suggesting).
                row_out.update(suggested_lane=row_out["decision"], decision="metadata", question="", options=[],
                               downgrade_reason="Suggested: your brief does not clearly ask for this to happen on its own.")
            else:
                row_out.update(decision="clarify",
                               downgrade_reason="This was not in your brief, so it is not built without your OK.")
        out.append(row_out)
    blocking = [r for r in out if r.get("decision") == "clarify" and not r.get("operator_confirmed")]
    for r in blocking[MAX_BLOCKING:]:
        # Past the question budget: left out (safe) and listed on the summary to add later.
        r.update(decision="declined", assumption="Left out for now; ask for it in a refine to add it.",
                 downgrade_reason="Left out for now; ask for it in a refine to add it.")
    return out


def apply_verifier_verdicts(
    requirements: list[dict[str, Any]], verdicts: dict[str, str] | None
) -> list[dict[str, Any]]:
    """Downgrade-only: a verifier can confirm, demote, or defer; never promote."""
    out = []
    for row in requirements:
        r = dict(row)
        if r["decision"] in _CODE_LANES and not r.get("operator_confirmed"):
            verdict = (verdicts or {}).get(r["id"])
            if verdict == "supports":
                r["verified"] = True
            elif verdict == "not_supported":
                r["decision"] = "metadata"
                r["downgrade_reason"] = "The cited text does not require automatic behavior."
            else:
                r["decision"] = "clarify"
                r["downgrade_reason"] = "The independent check was inconclusive."
        out.append(r)
    return out


_CONFLICT_PREFIX = "Your brief also says: "
_NEGATION = re.compile(
    r"(?i)\b(?:no|not|never|without|don'?t|do\s+not|shouldn'?t|must\s+not)\b[^.;\n]{0,60}"
)
# Behaviour families: a positive requirement and a negation conflict only when they
# talk about the same kind of automatic behaviour.
_BEHAVIOUR = {
    "compute": re.compile(r"(?i)\b(?:re)?(?:comput\w*|calculat\w*|derive\w*|formula\w*)"),
    "schedule": re.compile(r"(?i)\b(?:schedul\w*\s+(?:job|action|task)s?|nightly|every\s+night|cron\w*|daily\s+job)"),
    "remind": re.compile(r"(?i)\b(?:remind\w*|notif\w*|alert\w*|follow[\s-]?ups?)"),
    "python": re.compile(r"(?i)\b(?:python|custom\s+code)"),
    "automatic": re.compile(r"(?i)\bautomat\w*"),
}
_TRIGGER_CLASS = {"event": "auto", "time": "auto", "computation": "auto", "external": "auto",
                  "none": "entered", "user_entry": "entered"}


def _families(text: str) -> set[str]:
    return {k for k, rx in _BEHAVIOUR.items() if rx.search(text or "")}


def _quote(row: dict[str, Any]) -> str:
    ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    return str(ev.get("quote") or "")


def _words(row: dict[str, Any]) -> set[str]:
    return set(re.findall(r"[a-z0-9]{4,}", str(row.get("subject") or "").lower()))


def _same_behaviour(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ta, tb = str(a.get("target_model") or ""), str(b.get("target_model") or "")
    if ta and tb and ta != tb:
        return False
    shared = _words(a) & _words(b)
    fam = _families(f"{a.get('subject')} {_quote(a)}") & _families(f"{b.get('subject')} {_quote(b)}")
    return bool((ta and ta == tb and fam) or len(shared) >= 2 or (shared and fam))


def _heading_only(row: dict[str, Any]) -> bool:
    ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    return bool(ev.get("from_heading"))


def _mark_conflict(row: dict[str, Any], other_quote: str) -> dict[str, Any]:
    r = dict(row)
    r["decision"] = "clarify"
    r["verified"] = False
    r["downgrade_reason"] = (_CONFLICT_PREFIX + other_quote)[:160]
    return r


def detect_contract_conflicts(requirements: list[dict[str, Any]], prompt: str) -> list[dict[str, Any]]:
    """Deterministic conflict check (no LLM). A code-lane row that contradicts another
    row, or an explicit negation of the same behaviour in the brief, becomes ONE
    clarify question quoting both spans. Operator-confirmed rows are never touched."""
    rows = [dict(r) for r in requirements]
    for i, a in enumerate(rows):
        if a.get("operator_confirmed") or a.get("decision") not in _CODE_LANES or _heading_only(a):
            continue  # a section heading only shows the brief names it; too weak to prove a conflict
        hit = ""
        for j, b in enumerate(rows):
            if i == j or b.get("operator_confirmed") or _heading_only(b) or not _same_behaviour(a, b):
                continue
            ca = _TRIGGER_CLASS.get(str(a.get("trigger") or ""), "")
            cb = _TRIGGER_CLASS.get(str(b.get("trigger") or ""), "")
            wa, wb = _words(a), _words(b)
            same_subject = bool(wa and wb) and len(wa & wb) * 2 >= max(len(wa), len(wb))
            # A field, record or view the automation acts on is not a contradiction: only the
            # same behaviour described once as entered by people and once as automatic is.
            # The brief has to say people do it by hand; a model's "metadata" label alone is no evidence.
            lanes_clash = (
                b.get("decision") == "metadata"
                and b.get("kind") in {"automation", "python", "other"}
                and same_subject
                and bool(_MANUAL_CUE.search(_quote(b)))
                and not _AUTO_CUE.search(_quote(b))
            ) or (b.get("decision") in _CODE_LANES and ca and cb and ca != cb and same_subject)
            if lanes_clash and _quote(b) and _quote(b) != _quote(a):
                hit = _quote(b)
                if b.get("decision") in _CODE_LANES:
                    # Held back until the one question is answered.
                    rows[j] = dict(b, decision="metadata", verified=False,
                                   downgrade_reason="Held as a plain field until the conflict is answered.")
                break
        if not hit:
            fam = _families(f"{a.get('subject')} {_quote(a)}")
            for m in _NEGATION.finditer(prompt or ""):
                span = m.group(0).strip()
                if (m.start() and prompt[m.start() - 1] in "/(") or re.match(r"(?i)no\s*[)/,|]", span):
                    continue  # a yes/no field option, not the brief saying "don't"
                if _quote(a) and span in _quote(a):
                    continue
                if fam & _families(span):
                    hit = span
                    break
        if hit:
            rows[i] = _mark_conflict(a, hit)
    return rows


def apply_capability_policy(
    requirements: list[dict[str, Any]], known_models: set[str] | None
) -> list[dict[str, Any]]:
    """Deterministic check against the live registry; new x_* models are allowed."""
    if not known_models:
        return requirements
    out = []
    for row in requirements:
        r = dict(row)
        target = r.get("target_model") or ""
        if (
            r["decision"] == "stock_automation"
            and target
            and not target.startswith("x_")
            and target not in known_models
        ):
            r["decision"] = "clarify"
            r["downgrade_reason"] = f"{target} is not available in this database."
        out.append(r)
    return out


_NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
              "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14,
              "thirty": 30}
_OFFSET_RE = re.compile(
    r"(?i)\b(\d{1,4}|" + "|".join(_NUM_WORDS) + r")\s*-?\s*(day|week)s?\s+"
    r"(before|prior\s+to|ahead\s+of|ahead|earlier\s+than|after|following|past)\b")


def stated_day_offset(text: str) -> int | None:
    """Day offset the owner stated ("a week before" -> -7, "3 days after" -> 3); None if unstated.

    Code reads the number, unit and direction from the owner's own words, so an AI-proposed
    offset cannot silently become 0 or flip sign."""
    found = {m.group(0): m for m in _OFFSET_RE.finditer(text or "")}
    if len(found) != 1:
        return None  # none, or several different offsets: leave the proposal as it is
    m = next(iter(found.values()))
    raw = m.group(1).lower()
    n = int(raw) if raw.isdigit() else _NUM_WORDS[raw]
    days = n * (7 if m.group(2).lower() == "week" else 1)
    before = m.group(3).lower().split()[0] in {"before", "prior", "ahead", "earlier"}
    return -days if before else days


def stated_date_phrase(text: str) -> str:
    """The words naming the date right after a stated offset ("... a week before the decision
    date" -> "the decision date"); '' when no single offset is stated."""
    found = list(_OFFSET_RE.finditer(text or ""))
    if len({m.group(0) for m in found}) != 1:
        return ""
    rest = re.split(r"[.,;:!?\n]", (text or "")[found[0].end():], maxsplit=1)[0]
    return " ".join(rest.split()[:6])


def automations_from_contract(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stock automations the generator should create as data (no Python module)."""
    return [
        {
            "requirement_id": r["id"],
            "label": r["subject"],
            "trigger": r.get("trigger"),
            "target_model": r.get("target_model"),
            "mechanism": r.get("mechanism"),
            "automation": r.get("automation") or {},
            "evidence": r["evidence"],
        }
        for r in requirements
        if r.get("decision") == "stock_automation"
    ]


def bind_automation_targets(
    requirements: list[dict[str, Any]], models: dict[str, str]
) -> list[dict[str, Any]]:
    """Point each automation at a model that exists in the final design.

    The contract is extracted before the designer names its models, so the
    proposed target may not match. Keep dotted stock names, otherwise bind only
    on a single unambiguous word match; anything else is left unbound (and
    reported) rather than guessed.
    """
    out = []
    for row in requirements:
        r = dict(row)
        if r["decision"] == "stock_automation":
            target = r.get("target_model") or ""
            if target not in models and "." not in target:
                words = set(
                    re.findall(
                        r"[a-z0-9]{4,}",
                        f"{r['subject']} {r['evidence'].get('quote', '')} {target}".lower(),
                    )
                )
                hits = [
                    name
                    for name, label in models.items()
                    if words & set(re.findall(r"[a-z0-9]{4,}", f"{name} {label}".lower()))
                ]
                target = hits[0] if len(hits) == 1 else ""
            r["target_model"] = target
        out.append(r)
    return out


def resolve_contract_answers(
    requirements: list[dict[str, Any]], answers: dict[str, str] | None
) -> list[dict[str, Any]]:
    """Apply an explicit operator choice to an otherwise unresolved requirement."""
    resolved = answers or {}
    out: list[dict[str, Any]] = []
    for row in requirements:
        next_row = dict(row)
        raw_answer = str(resolved.get(f"intent_contract:{row.get('id')}") or "").strip()
        answer = raw_answer.split(":", 1)[0]
        picked = next((o for o in row.get("options") or [] if isinstance(o, dict) and raw_answer in {
            o.get("label"), o.get("decision")}), None)
        if picked is not None:
            answer = str(picked.get("decision") or "metadata")
        if row.get("decision") == "clarify" and raw_answer and answer not in {
            "metadata", "stock_automation", "option_a", "skip"}:
            # Typed in their own words: keep it as entered data and record the answer.
            next_row.update(decision="metadata", operator_confirmed=True, operator_answer=raw_answer[:240],
                            downgrade_reason="")
            out.append(next_row)
            continue
        if row.get("decision") == "clarify" and answer in {
            "metadata",
            "stock_automation",
            "option_a",
            "skip",
        }:
            next_row["decision"] = "declined" if answer == "skip" else answer
            next_row["operator_confirmed"] = True
            next_row["downgrade_reason"] = ""
            if answer == "option_a":
                next_row["why_metadata_cannot_do_it"] = (
                    "The operator chose custom code after App Studio surfaced the question."
                )
                next_row["metadata_alternative"] = "Fields, views, or standard automation"
        out.append(next_row)
    return out


def contract_requirement_for_piece(
    piece: dict[str, Any], requirements: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Return the matching custom code requirement without fuzzy single-word matches."""
    explicit = _identifier(piece.get("requirement_id") or piece.get("contract_id"), "")
    if explicit:
        return next(
            (r for r in requirements if r.get("id") == explicit and r.get("decision") == "option_a"),
            None,
        )
    label = _text(piece.get("label"), 100).lower()
    label_words = {
        w for w in re.findall(r"[a-z0-9]{4,}", label) if w not in {"custom", "python", "code"}
    }
    matches = []
    for row in requirements:
        if row.get("decision") != "option_a":
            continue
        subject_words = set(re.findall(r"[a-z0-9]{4,}", str(row.get("subject") or "").lower()))
        if label_words and len(label_words & subject_words) >= min(2, len(label_words)):
            matches.append(row)
    return matches[0] if len(matches) == 1 else None


def _bc_on() -> bool:
    from app.ai_conversation import brief_checklist as _bc

    return _bc.enabled()


def pending_contract_clarification(
    requirements: list[dict[str, Any]],
    _findings: list[dict[str, Any]] | None,
    answers: dict[str, str] | None,
) -> dict[str, Any] | None:
    """Build one precise question for the first unresolved requirement.

    Only the frozen contract can ask for a delivery decision; critic findings
    stay visible in the diagnosis but never create an authorization path.
    """
    resolved = answers or {}
    for row in requirements:
        if row.get("decision") != "clarify":
            continue
        key = f"intent_contract:{row.get('id')}"
        if str(resolved.get(key) or "").strip():
            continue
        evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        quote = str(evidence.get("quote") or "")
        subject = str(row.get("subject") or "this requirement")
        inferred = row.get("origin") == "inferred" or not quote
        if is_platform_constraint_question(row):
            continue
        if inferred and _bc_on():
            continue  # inferred extras are optional suggestions on the diagnosis, never blocking
        if _bc_on() and not (str(row.get("downgrade_reason") or "").startswith(_CONFLICT_PREFIX)
                             or row.get("blocking_reason") == "risk"):
            continue  # retired fallback: not a conflict or a risky item -> shown default, never blocking
        if inferred and not row.get("question") and not row.get("downgrade_reason") and row.get("kind") not in {"python", "host"}:
            continue  # an App Studio suggestion: listed on the diagnosis to keep or remove, never blocking
        if inferred and not row.get("question"):
            question = (
                f"Your brief doesn't mention '{subject}', but it usually comes with this kind "
                "of app. Should App Studio add it?"
            )
            help_text = "This is a suggestion from App Studio, not something you asked for."
        elif inferred:
            question = row["question"]
            help_text = "App Studio needs your answer on this before it designs it."
        elif str(row.get("downgrade_reason") or "").startswith(_CONFLICT_PREFIX):
            other = str(row["downgrade_reason"])[len(_CONFLICT_PREFIX):]
            question = (
                f"Your brief seems to say two different things about '{subject}'. "
                "Which one should App Studio build?"
            )
            help_text = f"Your brief says: {quote.rstrip('. ')}. It also says: {other.rstrip('. ')}."
        else:
            question = row.get("question") or (
                f"Should '{subject}' be a value people enter, or something Odoo does automatically?"
            )
            help_text = (
                f"Your brief says: {quote.rstrip('. ')}. "
                "Choose the behavior you want so App Studio does not make that assumption for you."
            )
        ai_opts = row.get("options") if isinstance(row.get("options"), list) else []
        if ai_opts:
            # Answers that answer the question; each maps to a build way decided in code.
            options = [{"id": o["decision"] if i == 0 or o["decision"] != ai_opts[0]["decision"] else f"{o['decision']}:{i}",
                        "label": o["label"], "decision": o["decision"]} for i, o in enumerate(ai_opts)]
        elif _BUILD_Q.search(question) or not row.get("question"):
            options = [
                {"id": "metadata", "label": "People fill it in"},
                {"id": "stock_automation", "label": "Odoo does it automatically"},
                {"id": "option_a", "label": "It needs custom code"},
            ]
        else:
            options = []  # the operator answers in their own words
        if inferred and not row.get("question"):
            options.insert(0, {"id": "skip", "label": "No, leave it out"})
        return {
            "id": f"intent-contract-{row.get('id')}",
            "kind": "intent_contract",
            "merge_key": key,
            "question": question,
            "help": help_text,
            "options": options,
            "default_id": "skip" if inferred else "metadata",
        }
    return None


def normalize_critic_findings(raw: Any, prompt: str) -> list[dict[str, Any]]:
    """Keep critic findings only when they point to a positive brief span."""
    entries = raw.get("findings") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(entries[:12]):
        if not isinstance(item, dict):
            continue
        kind = _text(item.get("kind"), 32).lower()
        if kind not in {"ambiguity", "missing_requirement", "unsupported_design"}:
            continue
        evidence = locate_evidence(
            prompt, _evidence_quote(item.get("evidence")) or item.get("quote")
        )
        subject = _text(item.get("subject"), 100)
        if evidence is None or not subject:
            continue
        finding_id = _identifier(item.get("id"), f"finding_{index + 1}")
        if finding_id in seen:
            continue
        out.append(
            {
                "id": finding_id,
                "kind": kind,
                "subject": subject,
                "evidence": evidence,
                "detail": _text(item.get("detail") or item.get("reason"), 240),
                "question": _text(item.get("question"), 240),
                "severity": _text(item.get("severity"), 12).lower() or "review",
            }
        )
        seen.add(finding_id)
    return out


__all__ = [
    "stated_date_phrase",
    "stated_day_offset",
    "apply_capability_policy",
    "apply_verifier_verdicts",
    "detect_contract_conflicts",
    "automations_from_contract",
    "contract_requirement_for_piece",
    "ladder_is_complete",
    "locate_evidence",
    "normalize_critic_findings",
    "normalize_intent_contract",
    "pending_contract_clarification",
    "resolve_contract_answers",
    "bind_automation_targets",
]
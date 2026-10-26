"""Business fit-gap: classify document steps / requirements against stock Odoo (read-only).

Verdicts per step: stock | stock-with-config | partial | custom (with reasons). Availability comes
from the live module snapshot (`ir.module.module` name/state/latest_version), so an
Enterprise-only feature on a Community database is reported as a gap, never as stock.

Matching is layered. (1) The deterministic matcher (zero tokens): generic concept table
(`fitgap_table.json`, modules checked against `inventory.gen.json`) plus any industry packs
(`packs.json`) selected by document content. (2) Steps it cannot confirm may go to ONE batched
model call (`suggest.py`) that can only pick a concept id, 'custom' or 'unknown'; such steps
are labelled 'model-suggested' and never add plan actions.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from app.bots.fitgap.ingest import FlowGraph

TABLE_PATH = Path(__file__).with_name("fitgap_table.json")
PACKS_PATH = Path(__file__).with_name("packs.json")
MAJORS = (17, 18, 19, 20)
MAX_PACKS = 2
Verdict = Literal["stock", "stock-with-config", "partial", "custom"]
Confidence = Literal[
    "strong pattern", "strong + context", "weak + context", "model-suggested", "needs human"
]
ENTERPRISE_MARKER = "web_enterprise"
Guard = tuple[re.Pattern[str], frozenset[str]]  # (pattern, areas it does NOT block)


@dataclass(frozen=True)
class Concept:
    id: str
    label: str
    module: str
    min_major: int
    edition: str
    patterns: tuple[tuple[re.Pattern[str], bool], ...]  # (word-start regex, strong)
    setup: tuple[dict[str, Any], ...]
    negative: tuple[re.Pattern[str], ...] = ()
    area: str = "other"


@dataclass(frozen=True)
class Gap:
    id: str
    label: str
    reason: str
    patterns: tuple[re.Pattern[str], ...]
    spec: dict[str, Any]
    area: str = "other"
    concept: str | None = None  # a known limit of this concept (fires only with it)


@dataclass(frozen=True)
class Question:
    text: str
    concepts: frozenset[str]
    when: re.Pattern[str] | None
    unless: re.Pattern[str] | None


@dataclass(frozen=True)
class Table:
    concepts: tuple[Concept, ...]
    gaps: tuple[Gap, ...]
    negative: tuple[Guard, ...]
    context: tuple[re.Pattern[str], ...]
    office: tuple[Guard, ...] = ()  # office/admin words: block concepts, not gaps
    questions: tuple[Question, ...] = ()
    packs: tuple[str, ...] = ()


def _compile(pats: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    """Word-start matching: 'grad' hits 'grading', never 'upgrade'."""
    return tuple(re.compile(rf"(?<!\w)(?:{p})", re.I) for p in pats)


def _guards(raw: Iterable[Any]) -> tuple[Guard, ...]:
    out = []
    for x in raw:
        p, exc = (x, ()) if isinstance(x, str) else (x["p"], x.get("except", ()))
        out.append((_compile([p])[0], frozenset(exc)))
    return tuple(out)


def _pats(raw: Iterable[Mapping[str, str]], where: str) -> tuple[tuple[re.Pattern[str], bool], ...]:
    raw = list(raw)
    if any(x.get("w") not in ("strong", "weak") for x in raw):
        raise ValueError(f"pattern strength missing in {where}")
    return tuple(zip(_compile(x["p"] for x in raw), (x["w"] == "strong" for x in raw), strict=True))


def _gap(g: Mapping[str, Any]) -> Gap:
    return Gap(
        g["id"],
        g["label"],
        g["reason"],
        _compile(g["patterns"]),
        {k: g[k] for k in ("model", "depends", "fields")},
        g.get("area", "other"),
        g.get("concept"),
    )


def _question(q: Mapping[str, Any]) -> Question:
    when, unless = q.get("if"), q.get("unless")
    return Question(
        q["text"],
        frozenset(q.get("concepts", ())),
        re.compile(when, re.I) if when else None,
        re.compile(unless, re.I) if unless else None,
    )


@lru_cache(maxsize=1)
def load_raw(path: str = str(TABLE_PATH)) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


@lru_cache(maxsize=1)
def load_packs(path: str = str(PACKS_PATH)) -> dict[str, dict[str, Any]]:
    packs = {p["id"]: p for p in json.loads(Path(path).read_text())["packs"]}
    for p in packs.values():
        if not p.get("signals"):
            raise ValueError(f"pack {p['id']} has no signals")
    return packs


@lru_cache(maxsize=16)
def load_table(path: str = str(TABLE_PATH), packs: tuple[str, ...] = ()) -> Table:
    raw = load_raw(path)
    pk = load_packs()
    chosen = [pk[i] for i in packs]
    concepts = []
    for c in raw["concepts"]:
        if c["edition"] not in ("community", "enterprise") or c["min_major"] not in MAJORS:
            raise ValueError(f"bad concept {c['id']}")
        extra = [x for p in chosen for x in p.get("patterns", {}).get(c["id"], ())]
        concepts.append(
            Concept(
                c["id"],
                c["label"],
                c["module"],
                c["min_major"],
                c["edition"],
                _pats(list(c["patterns"]) + extra, c["id"]),
                tuple(c["setup"]),
                _compile(c.get("negative", ())),
                c.get("area", "other"),
            )
        )
    known = {c.id for c in concepts}
    limits = [
        Gap(
            f"limit:{c['id']}:{lim['id']}",
            f"{c['label']}: {lim['id'].replace('_', ' ')}",
            f"stated limit of standard Odoo: {lim['reason']}",
            _compile(lim["patterns"]),
            {
                "model": f"ingenium.{c['id']}_{lim['id']}",
                "depends": [c["module"]],
                "fields": [{"name": "name", "ttype": "char", "string": "Name", "required": True}],
            },
            c.get("area", "other"),
            c["id"],
        )
        for c in raw["concepts"]
        for lim in c.get("known_limits", ())
    ]
    for p in chosen:
        if bad := set(p.get("patterns", {})) - known:
            raise ValueError(f"pack {p['id']} names unknown concepts {sorted(bad)}")
    gaps = (
        limits
        + [_gap(g) for g in raw["gaps"]]
        + [_gap(g) for p in chosen for g in p.get("gaps", ())]
    )
    ids = [c.id for c in concepts] + [g.id for g in gaps]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate concept/gap id")
    if any(g.concept and g.concept not in known for g in gaps):
        raise ValueError("limit names an unknown concept")
    return Table(
        tuple(concepts),
        tuple(gaps),
        _guards(raw["negative"]),
        _compile(list(raw["context"]) + [x for p in chosen for x in p.get("context", ())]),
        _guards(raw["office"]),
        tuple(_question(q) for p in chosen for q in p.get("questions", ())),
        tuple(packs),
    )


def select_packs(graph: FlowGraph) -> tuple[str, ...]:
    """Industry packs whose signal words appear in the document (most distinct hits first)."""
    corpus = " ".join([s.text for s in graph.steps] + graph.notes)
    score = {
        pid: sum(1 for p in _compile(pack["signals"]) if p.search(corpus))
        for pid, pack in load_packs().items()
    }
    best = max(score.values(), default=0)
    if not best:
        return ()
    ranked = sorted(
        (pid for pid, n in score.items() if n * 2 >= best and n), key=lambda i: (-score[i], i)
    )
    return tuple(sorted(ranked[:MAX_PACKS]))


@dataclass(frozen=True)
class OdooEnv:
    major: int
    edition: Literal["community", "enterprise"]
    installed: frozenset[str]
    installable: frozenset[str]

    @classmethod
    def from_modules(
        cls, major: int, installed: Iterable[str], installable: Iterable[str] = ()
    ) -> OdooEnv:
        if major not in MAJORS:
            raise ValueError(f"unsupported Odoo major {major}")
        inst, avail = frozenset(installed), frozenset(installable)
        ed = "enterprise" if ENTERPRISE_MARKER in inst | avail else "community"
        return cls(major, ed, inst, avail - inst)  # type: ignore[arg-type]


def read_env(call: Callable[[str, str, list[Any], dict[str, Any]], Any]) -> OdooEnv:
    """One read: `ir.module.module.search_read`. Unreadable -> ValueError (fail closed)."""
    rows = call(
        "ir.module.module",
        "search_read",
        [[["state", "in", ["installed", "to upgrade", "uninstalled", "to install"]]]],
        {"fields": ["name", "state", "latest_version"]},
    )
    if not isinstance(rows, list):
        raise ValueError("module list unreadable")
    installed, avail, base_ver = set(), set(), ""
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("name"), str):
            continue
        (installed if r.get("state") in ("installed", "to upgrade") else avail).add(r["name"])
        if r["name"] == "base":
            base_ver = str(r.get("latest_version") or "")
    m = re.search(r"(?:saas~)?(\d{2})\.", base_ver)
    if not m or "base" not in installed:
        raise ValueError("Odoo version not determinable from base module")
    return OdooEnv.from_modules(int(m.group(1)), installed, avail)


@dataclass
class ConceptUse:
    concept: str
    label: str
    module: str
    status: Literal["ready", "install", "unavailable", "unverified"]
    reason: str


@dataclass
class StepFit:
    step_id: str
    text: str
    verdict: Verdict | None  # None: event/gateway, nothing to map
    concepts: list[ConceptUse] = field(default_factory=list)
    gap: str | None = None
    reasons: list[str] = field(default_factory=list)
    needs_human: bool = False
    confidence: Confidence = "needs human"
    area: str = "unassigned"
    priority: str | None = None
    quote: str | None = None  # model path: the words of the step it relied on

    @property
    def confirmed(self) -> bool:
        """A fit backed by a strong deterministic match (weak and model matches are not)."""
        return self.verdict in ("stock", "stock-with-config") and self.confidence in (
            "strong pattern",
            "strong + context",
        )


@dataclass
class FitGap:
    env: OdooEnv | None
    steps: list[StepFit]
    verdict: Verdict
    questions: list[str]
    gaps: list[str]
    packs: tuple[str, ...] = ()
    stubs: dict[str, dict[str, Any]] = field(default_factory=dict)
    model_calls: int = 0
    notes: list[str] = field(default_factory=list)
    merged: int = 0  # repeated identical steps counted once

    @property
    def enough_input(self) -> bool:
        """False when nothing usable was read: no mapped step, or every one needs a human."""
        mapped = [f for f in self.steps if f.verdict]
        return bool(mapped) and not all(f.needs_human for f in mapped)

    @property
    def overall(self) -> str:
        """Headline verdict. Fits backed only by weak or model matches are 'suggested-fit',
        never 'stock'; nothing usable read is 'not-enough-input'."""
        if not self.enough_input:
            return "not-enough-input"
        if self.verdict in ("custom", "partial"):
            return self.verdict
        if any(f.verdict and not f.confirmed for f in self.steps):
            return "suggested-fit"
        return self.verdict

    def area_fit(self) -> dict[str, dict[str, Any]]:
        """Per area: mapped steps; 'fit' counts only confirmed (strong deterministic) fits and is
        the headline percent; weak/model fits are counted apart as 'suggested'."""
        out: dict[str, dict[str, Any]] = {}
        for f in self.steps:
            if not f.verdict:
                continue
            a = out.setdefault(f.area, {"steps": 0, "fit": 0, "suggested": 0})
            a["steps"] += 1
            a["fit"] += f.confirmed
            a["suggested"] += f.verdict in ("stock", "stock-with-config") and not f.confirmed
        for a in out.values():
            a["percent"] = round(100 * a["fit"] / a["steps"])
            a["percent_incl_suggestions"] = round(100 * (a["fit"] + a["suggested"]) / a["steps"])
        return dict(sorted(out.items()))

    def fit_percent(self) -> tuple[int, int]:
        """(confirmed %, including suggestions %) over all mapped steps."""
        m = [f for f in self.steps if f.verdict]
        if not m:
            return 0, 0
        ok = sum(f.confirmed for f in m)
        sug = sum(f.verdict in ("stock", "stock-with-config") and not f.confirmed for f in m)
        return round(100 * ok / len(m)), round(100 * (ok + sug) / len(m))

    def to_dict(self) -> dict[str, Any]:
        env = None if self.env is None else {"major": self.env.major, "edition": self.env.edition}
        return {
            "env": env,
            "verdict": self.verdict,
            "overall": self.overall,
            "enough_input": self.enough_input,
            "confirmed_fit_percent": self.fit_percent()[0],
            "fit_percent_incl_suggestions": self.fit_percent()[1],
            "questions": self.questions,
            "gaps": self.gaps,
            "packs": list(self.packs),
            "area_fit": self.area_fit(),
            "stubs": self.stubs,
            "model_calls": self.model_calls,
            "merged_repeats": self.merged,
            "steps": [
                {
                    "step_id": s.step_id,
                    "text": s.text,
                    "verdict": s.verdict,
                    "gap": s.gap,
                    "needs_human": s.needs_human,
                    "match_confidence": s.confidence,
                    "area": s.area,
                    "priority": s.priority,
                    "quote": s.quote,
                    "reasons": s.reasons,
                    "concepts": [vars(c) for c in s.concepts],
                }
                for s in self.steps
            ],
        }


def _availability(c: Concept, env: OdooEnv | None) -> ConceptUse:
    def use(status: Any, reason: str) -> ConceptUse:
        return ConceptUse(c.id, c.label, c.module, status, reason)

    if env is None:
        if c.edition == "enterprise":
            return use("unverified", f"{c.label} needs Enterprise unless confirmed")
        return use("unverified", f"needs module {c.module}; database not checked")
    if env.major < c.min_major:
        return use("unavailable", f"{c.label} needs Odoo {c.min_major}+")
    if c.edition == "enterprise" and env.edition != "enterprise":
        return use(
            "unavailable", f"{c.label} is Enterprise only ({c.module}); this database is Community"
        )
    if c.module in env.installed:
        return use("ready", f"{c.module} installed")
    if c.module in env.installable:
        return use("install", f"install {c.module}")
    return use("unavailable", f"module {c.module} not available on this database")


def _hit(pats: Iterable[re.Pattern[str]], text: str) -> bool:
    return any(p.search(text) for p in pats)


def _guarded(guards: Iterable[Guard], text: str, area: str) -> bool:
    """A negative/office word blocks every area except the ones it names."""
    return any(area not in exc and p.search(text) for p, exc in guards)


def _spans(c: Concept, text: str) -> list[tuple[int, int, bool]]:
    if _hit(c.negative, text):
        return []
    return [(m.start(), m.end(), st) for p, st in c.patterns for m in p.finditer(text)]


def _open(t: Table, text: str) -> list[Concept]:
    return [
        c
        for c in t.concepts
        if not _guarded(t.negative, text, c.area) and not _guarded(t.office, text, c.area)
    ]


def _concepts(t: Table, text: str) -> list[Concept] | None:
    """None = needs a human.

    A concept counts when it has a STRONG hit, or a weak hit confirmed in the SAME step by any
    strong hit or by an operations-vocabulary noun that is not itself a keyword match. Weak
    words never confirm weak words; there is no document-level relaxation. Negative and office
    words block every concept outside the areas they explicitly exempt.
    """
    allowed = _open(t, text)
    if not allowed:
        return None
    hits = {c.id: _spans(c, text) for c in allowed}
    keyword = [(a, b) for c in t.concepts for a, b, _ in _spans(c, text)]
    strong = any(st for hs in hits.values() for *_, st in hs)
    vocab = any(
        not any(m.start() < b and a < m.end() for a, b in keyword)
        for p in t.context
        for m in p.finditer(text)
    )
    out = [
        c for c in allowed if any(st for *_, st in hits[c.id]) or (hits[c.id] and (strong or vocab))
    ]
    return out or None


def _confidence(t: Table, text: str) -> Confidence:
    """How the step's concepts were matched (shown to the user as a suggestion strength)."""
    found = _concepts(t, text)
    if not found:
        return "needs human"
    strong = any(st for c in found for *_, st in _spans(c, text))
    if strong:
        return "strong + context" if _hit(t.context, text) else "strong pattern"
    return "weak + context"


def _gap_for(t: Table, text: str, matched: set[str]) -> Gap | None:
    for g in t.gaps:
        if g.concept is not None and g.concept not in matched:
            continue
        if _guarded(t.negative, text, g.area):
            continue
        if _hit(g.patterns, text):
            return g
    return None


def _blocked(c: ConceptUse, concepts: dict[str, Concept]) -> bool:
    """Unavailable, or Enterprise-only on an unchecked database (fail closed)."""
    return c.status == "unavailable" or (
        c.status == "unverified" and concepts[c.concept].edition == "enterprise"
    )


def _verdict(f: StepFit, t: Table, byc: dict[str, Concept]) -> None:
    usable = [c for c in f.concepts if not _blocked(c, byc)]
    f.reasons = [c.reason for c in f.concepts]
    if not usable:
        f.verdict = "custom"
        return
    blocked = [c for c in f.concepts if _blocked(c, byc)]
    if blocked:  # partial: never a confirmed fit; names what is missing on this edition
        f.verdict = "partial"
        f.reasons = [f"missing on this edition: {c.reason}" for c in blocked] + [
            f"available: {c.reason}" for c in usable
        ]
        return
    setup = any(byc[c.concept].setup for c in usable)
    pending = any(c.status != "ready" for c in usable)
    f.verdict = "stock-with-config" if setup or pending else "stock"


def _slug(text: str) -> str:
    return "_".join(re.findall(r"[a-z0-9]+", text.lower()))[:40] or "step"


def classify(
    graph: FlowGraph,
    env: OdooEnv | None,
    table: Table | None = None,
    *,
    suggest: Callable[..., Any] | None = None,
) -> FitGap:
    t = table or load_table(packs=select_packs(graph))
    fits: list[StepFit] = []
    byc = {c.id: c for c in t.concepts}
    seen: set[str] = set()
    merged = 0
    for s in graph.order():
        text = s.text
        norm = " ".join(re.findall(r"\w+", text.casefold()))
        if s.kind not in ("event", "gateway") and norm:
            if norm in seen:  # identical step repeated: counted once
                merged += 1
                continue
            seen.add(norm)
        if s.kind in ("event", "gateway"):
            fits.append(StepFit(s.id, text, None, reasons=[f"{s.kind}: flow control only"]))
            continue
        f = StepFit(s.id, text, "custom", priority=getattr(s, "priority", None))
        found = _concepts(t, text) or []
        gap = _gap_for(t, text, {c.id for c in found})
        f.concepts = [_availability(c, env) for c in found]
        f.confidence = "needs human" if gap is not None else _confidence(t, text)
        if found:
            f.area = found[0].area
        if gap is not None:
            f.gap, f.reasons, f.area = gap.id, [gap.reason], gap.area
        elif not f.concepts:
            f.needs_human = True
            f.reasons = ["not recognised as a standard Odoo step; needs a human or custom work"]
        else:
            _verdict(f, t, byc)
        fits.append(f)
    calls = 0
    notes: list[str] = []
    open_ = [f for f in fits if f.needs_human]
    if suggest is not None and open_:
        from app.bots.fitgap import suggest as sg

        calls = 1
        got = sg.run(
            suggest, [(f.step_id, f.text) for f in open_], {c.id: c.label for c in t.concepts}
        )
        notes += got.notes
        for f in open_:
            pick = got.picks.get(f.step_id)
            if pick is None:
                continue
            f.quote, f.confidence = pick.quote, "model-suggested"
            if pick.choice == "unknown":
                f.reasons = [f"model could not tell: {pick.reason}"]
                continue
            f.needs_human = False
            if pick.choice == "custom":
                f.verdict, f.area = "custom", "unassigned"
                f.gap = f"custom:{f.step_id}"
                f.reasons = [f"model-suggested custom work: {pick.reason}"]
                continue
            c = byc[pick.choice]
            f.concepts, f.area = [_availability(c, env)], c.area
            _verdict(f, t, byc)
            f.reasons.insert(0, f"model-suggested ({pick.reason}); please confirm")
    mapped = [f for f in fits if f.verdict]
    verdict: Verdict = (
        "custom"
        if not mapped or all(f.needs_human for f in mapped)  # fail closed: nothing to go on
        else "custom"
        if any(f.verdict == "custom" for f in mapped)
        else "partial"
        if any(f.verdict == "partial" for f in mapped)
        else "stock-with-config"
        if any(f.verdict == "stock-with-config" for f in mapped)
        else "stock"
    )
    gaps = list(
        dict.fromkeys(
            [f.gap for f in fits if f.gap]
            + [f"unknown:{f.step_id}" for f in fits if f.needs_human]
            + [
                f"unavailable:{c.concept}"
                for f in fits
                if f.verdict in ("custom", "partial") and not f.gap
                for c in f.concepts
                if _blocked(c, byc)
            ]
        )
    )
    stubs = {
        g: {
            "model": f"x_ingenium_{_slug(f.text)}",
            "description": f.text[:120],
            "fields": [{"name": "name", "ttype": "char", "string": "Name", "required": True}],
            "status": "stub: to be designed after a person confirms the step",
        }
        for f in fits
        for g in ([f.gap] if f.gap and f.gap.startswith("custom:") else [])
        + ([f"unknown:{f.step_id}"] if f.needs_human else [])
    }
    return FitGap(
        env,
        fits,
        verdict,
        _questions(t, graph, fits, env),
        gaps,
        t.packs,
        stubs,
        calls,
        notes,
        merged,
    )


def _questions(t: Table, graph: FlowGraph, fits: list[StepFit], env: OdooEnv | None) -> list[str]:
    """Only questions whose answer can change a verdict: the target database (availability),
    and pack questions about concepts that are still a fit (the answer may make them custom)."""
    corpus = " ".join([s.text for s in graph.steps] + graph.notes)
    qs: list[str] = []
    if env is None:
        qs.append("Which Odoo version and edition (Community or Enterprise) will you run?")
    open_concepts = {
        c.concept for f in fits if f.verdict in ("stock", "stock-with-config") for c in f.concepts
    }
    for q in t.questions:
        if q.when is not None and not q.when.search(corpus):
            continue
        if q.unless is not None and q.unless.search(corpus):
            continue
        if q.concepts and not q.concepts & open_concepts:
            continue
        if not q.concepts and not open_concepts:
            continue
        qs.append(q.text)
    return qs

"""Fit-gap of a FlowGraph against stock Odoo for one connected database (read-only).

Verdicts per step: stock | stock-with-config | custom (with reasons). Availability comes
from the live module snapshot (`ir.module.module` name/state/latest_version), so an
Enterprise-only feature on a Community database is reported as a gap, never as stock.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from app.bots.process.ingest import FlowGraph

TABLE_PATH = Path(__file__).with_name("fitgap_table.json")
MAJORS = (17, 18, 19, 20)
Verdict = Literal["stock", "stock-with-config", "custom"]
Confidence = Literal["strong pattern", "strong + context", "weak + context", "needs human"]
ENTERPRISE_MARKER = "web_enterprise"


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


@dataclass(frozen=True)
class Gap:
    id: str
    label: str
    reason: str
    patterns: tuple[re.Pattern[str], ...]
    spec: dict[str, Any]


@dataclass(frozen=True)
class Table:
    concepts: tuple[Concept, ...]
    gaps: tuple[Gap, ...]
    negative: tuple[re.Pattern[str], ...]
    context: tuple[re.Pattern[str], ...]
    office: tuple[re.Pattern[str], ...] = ()  # office/admin words: block concepts, not gaps


def _compile(pats: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    """Word-start matching: 'grad' hits 'grading', never 'upgrade'."""
    return tuple(re.compile(rf"(?<!\w)(?:{p})", re.I) for p in pats)


@lru_cache(maxsize=1)
def load_table(path: str = str(TABLE_PATH)) -> Table:
    raw = json.loads(Path(path).read_text())
    concepts = []
    for c in raw["concepts"]:
        if c["edition"] not in ("community", "enterprise") or c["min_major"] not in MAJORS:
            raise ValueError(f"bad concept {c['id']}")
        if any(x.get("w") not in ("strong", "weak") for x in c["patterns"]):
            raise ValueError(f"pattern strength missing in {c['id']}")
        pats = tuple(
            zip(
                _compile(x["p"] for x in c["patterns"]),
                (x["w"] == "strong" for x in c["patterns"]),
                strict=True,
            )
        )
        concepts.append(
            Concept(
                c["id"],
                c["label"],
                c["module"],
                c["min_major"],
                c["edition"],
                pats,
                tuple(c["setup"]),
                _compile(c.get("negative", ())),
            )
        )
    gaps = [
        Gap(
            g["id"],
            g["label"],
            g["reason"],
            _compile(g["patterns"]),
            {k: g[k] for k in ("model", "depends", "fields")},
        )
        for g in raw["gaps"]
    ]
    ids = [c.id for c in concepts] + [g.id for g in gaps]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate concept/gap id")
    return Table(
        tuple(concepts),
        tuple(gaps),
        _compile(raw["negative"]),
        _compile(raw["context"]),
        _compile(raw["office"]),
    )


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


@dataclass
class FitGap:
    env: OdooEnv | None
    steps: list[StepFit]
    verdict: Verdict
    questions: list[str]
    gaps: list[str]

    def to_dict(self) -> dict[str, Any]:
        env = None if self.env is None else {"major": self.env.major, "edition": self.env.edition}
        return {
            "env": env,
            "verdict": self.verdict,
            "questions": self.questions,
            "gaps": self.gaps,
            "steps": [
                {
                    "step_id": s.step_id,
                    "text": s.text,
                    "verdict": s.verdict,
                    "gap": s.gap,
                    "needs_human": s.needs_human,
                    "match_confidence": s.confidence,
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


def _spans(c: Concept, text: str) -> list[tuple[int, int, bool]]:
    if _hit(c.negative, text):
        return []
    return [(m.start(), m.end(), st) for p, st in c.patterns for m in p.finditer(text)]


def _concepts(t: Table, text: str) -> list[Concept] | None:
    """None = needs a human.

    A concept counts when it has a STRONG hit, or a weak hit confirmed in the SAME step by any
    strong hit or by an operations-vocabulary noun that is not itself a keyword match. Weak
    words never confirm weak words; there is no document-level relaxation.
    """
    if _hit(t.negative, text) or _hit(t.office, text):
        return None
    hits = {c.id: _spans(c, text) for c in t.concepts}
    keyword = [(a, b) for hs in hits.values() for a, b, _ in hs]
    strong = any(st for hs in hits.values() for *_, st in hs)
    vocab = any(
        not any(m.start() < b and a < m.end() for a, b in keyword)
        for p in t.context
        for m in p.finditer(text)
    )
    out = [
        c
        for c in t.concepts
        if any(st for *_, st in hits[c.id]) or (hits[c.id] and (strong or vocab))
    ]
    return out or None


def _confidence(t: Table, text: str) -> Confidence:
    """How the step's concepts were matched (shown to the user as a suggestion strength)."""
    if not _concepts(t, text):
        return "needs human"
    strong = any(st for c in t.concepts for *_, st in _spans(c, text))
    vocab = _hit(t.context, text)
    if strong:
        return "strong + context" if vocab else "strong pattern"
    return "weak + context"


def _blocked(c: ConceptUse, concepts: dict[str, Concept]) -> bool:
    """Unavailable, or Enterprise-only on an unchecked database (fail closed)."""
    return c.status == "unavailable" or (
        c.status == "unverified" and concepts[c.concept].edition == "enterprise"
    )


def classify(graph: FlowGraph, env: OdooEnv | None, table: Table | None = None) -> FitGap:
    t = table or load_table()
    fits: list[StepFit] = []
    byc = {c.id: c for c in t.concepts}
    for s in graph.order():
        text = s.text
        if s.kind in ("event", "gateway"):
            fits.append(StepFit(s.id, text, None, reasons=[f"{s.kind}: flow control only"]))
            continue
        f = StepFit(s.id, text, "custom")
        neg = _hit(t.negative, text)
        gap = None if neg else next((g for g in t.gaps if _hit(g.patterns, text)), None)
        f.concepts = [_availability(c, env) for c in _concepts(t, text) or []]
        f.confidence = "needs human" if gap is not None else _confidence(t, text)
        if gap is not None:
            f.gap, f.reasons = gap.id, [gap.reason]
        elif not f.concepts:
            f.needs_human = True
            f.reasons = ["not recognised as a standard Odoo step; needs a human or custom work"]
        else:
            usable = [c for c in f.concepts if not _blocked(c, byc)]
            f.reasons = [c.reason for c in f.concepts]
            if not usable:
                f.verdict = "custom"
            else:
                setup = any(next(x for x in t.concepts if x.id == c.concept).setup for c in usable)
                pending = any(c.status != "ready" for c in usable)
                f.verdict = "stock-with-config" if setup or pending else "stock"
                f.reasons += [
                    f"partly unavailable: {c.reason}" for c in f.concepts if _blocked(c, byc)
                ]
        fits.append(f)
    mapped = [f for f in fits if f.verdict]
    verdict: Verdict = (
        "custom"
        if any(f.verdict == "custom" for f in mapped)
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
                if f.verdict == "custom" and not f.gap
                for c in f.concepts
                if _blocked(c, byc)
            ]
        )
    )
    return FitGap(env, fits, verdict, _questions(graph, fits, env), gaps)


def _questions(graph: FlowGraph, fits: list[StepFit], env: OdooEnv | None) -> list[str]:
    corpus = " ".join([s.text for s in graph.steps] + graph.notes).lower()
    qs: list[str] = []
    if env is None:
        qs.append("Which Odoo version and edition (Community or Enterprise) will you run?")
    if any(c.concept == "manufacturing" for f in fits for c in f.concepts) and not re.search(
        r"\bbatch(es)?\b|continuous", corpus
    ):
        qs.append("Is milling run in separate batches or as one continuous line?")
    if re.search(r"weigh|scale|metal detect|sensor|plc", corpus) and not re.search(
        r"\biot\b|manual(ly)? (entry|record)|connected", corpus
    ):
        qs.append(
            "Are scales and detectors connected to a computer, or are readings typed in by hand?"
        )
    return qs

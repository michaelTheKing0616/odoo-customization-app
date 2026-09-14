"""Domain-agnostic pack routing and draft coherence — any vertical, not marker lists."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.ai_domain_nouns import extract_prompt_nouns
from app.ai_post_critique import NOUN_STOPWORDS
from app.text_negation import has_positive_match

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)

# Regex-suggested packs may have lower token overlap; Jaccard-only retrieval uses the stricter floor.
PACK_MERGE_MIN_JACCARD = 0.10
PACK_MERGE_MIN_JACCARD_REGEX = 0.04
# Top pack must beat the runner-up by at least this margin when scores are low.
PACK_MERGE_MIN_MARGIN = 0.03
# Low-score ambiguity band — refuse merge when top two packs tie here.
PACK_AMBIGUOUS_TOP_SCORE = 0.15
# Drop a custom model when prompt alignment is below this and industry clusters disagree.
MODEL_ALIGN_MIN = 0.08
MODEL_ALIGN_MIN_WITH_CLUSTER_CONFLICT = 0.18

# Tokens too generic to infer an industry cluster from alone.
_GENERIC_CLUSTER_TOKENS = frozenset(
    {
        "management",
        "system",
        "operations",
        "operation",
        "record",
        "data",
        "custom",
        "model",
        "field",
        "workflow",
        "status",
        "order",
        "line",
        "item",
        "company",
        "partner",
        "user",
        "mail",
        "base",
        "branch",
        "branches",
        "world",
        "global",
        "international",
        "multiple",
        "large",
        "small",
        "internal",
        "portal",
        "report",
        "dashboard",
        # Function words leak from pack descriptions ("before (or while) a matter is open").
        # Overlap on "and"/"the" must not infer law_firm from an oil-and-gas prompt.
        *NOUN_STOPWORDS,
        "before",
        "while",
        "never",
        "not",
        "off",
        "sit",
        "hang",
        "type",
        "version",
        "parallel",
        "linked",
        "they",
        "does",
        "replace",
        "only",
        "via",
        "use",
        "than",
        "then",
        "when",
        "who",
        "which",
        "what",
        "how",
        "into",
    }
)


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) > 2}


def _model_blob(model: dict[str, Any]) -> str:
    parts = [
        str(model.get("model") or ""),
        str(model.get("description") or ""),
    ]
    for field in model.get("fields") or []:
        if isinstance(field, dict):
            parts.append(str(field.get("name") or ""))
            parts.append(str(field.get("string") or ""))
    return " ".join(parts).lower()


@lru_cache(maxsize=1)
def industry_cluster_keywords() -> dict[str, frozenset[str]]:
    """Industry keyword sets derived from curated packs + stable generic clusters."""
    from app.ai_domain_packs import _PACK_FACTORIES

    clusters: dict[str, set[str]] = {
        "generic_ops": {
            "staff",
            "shift",
            "compliance",
            "deposit",
            "event",
            "task",
            "document",
        },
    }
    for pack_id, factory, _pattern in _PACK_FACTORIES:
        pack = factory()
        bag: set[str] = set(_tokenize(pack_id.replace("_", " ")))
        for tag in pack.get("tags") or []:
            bag |= _tokenize(str(tag))
        for model in pack.get("models") or []:
            if not isinstance(model, dict):
                continue
            mid = str(model.get("model") or "")
            # Inherit stock hosts are reuse, not industry signal (account.move ≠ law_firm).
            if mid.startswith("x_"):
                bag |= _tokenize(mid.replace("x_", "").replace("_", " "))
                bag |= _tokenize(str(model.get("description") or ""))
        clusters[pack_id] = {
            t for t in bag if t not in _GENERIC_CLUSTER_TOKENS and len(t) >= 3
        }
    return {k: frozenset(v) for k, v in clusters.items() if v}


@lru_cache(maxsize=1)
def _shared_cluster_tokens() -> frozenset[str]:
    """Tokens that appear in multiple industry clusters — weak industry signals alone."""
    clusters = industry_cluster_keywords()
    counts: dict[str, int] = {}
    for keywords in clusters.values():
        for token in keywords:
            counts[token] = counts.get(token, 0) + 1
    return frozenset(token for token, count in counts.items() if count > 1)


def _distinctive_cluster_tokens(industry: str) -> frozenset[str]:
    shared = _shared_cluster_tokens()
    return industry_cluster_keywords().get(industry, frozenset()) - shared


def infer_prompt_industries(prompt: str) -> set[str]:
    """Industries implied by the user prompt (may be empty for novel domains)."""
    pt = {
        t
        for t in (_tokenize(prompt) | set(extract_prompt_nouns(prompt)))
        if t not in _GENERIC_CLUSTER_TOKENS
    }
    hits: set[str] = set()
    for industry, keywords in industry_cluster_keywords().items():
        if pt & keywords:
            hits.add(industry)
    return hits


def infer_model_industries(model: dict[str, Any]) -> set[str]:
    """Industries a custom model reads as belonging to."""
    blob = _model_blob(model)
    blob_tokens = _tokenize(blob)
    hits: set[str] = set()
    for industry in industry_cluster_keywords():
        keywords = _distinctive_cluster_tokens(industry)
        if not keywords:
            continue
        if blob_tokens & keywords:
            hits.add(industry)
            continue
        if any(k in blob for k in keywords if len(k) >= 5):
            hits.add(industry)
    return hits


def score_model_prompt_alignment(model: dict[str, Any], prompt: str) -> float:
    """Token overlap between prompt and a model's id/labels (0..1 Jaccard)."""
    pt = _tokenize(prompt)
    pt |= set(extract_prompt_nouns(prompt))
    if not pt:
        return 0.0
    mt = _tokenize(_model_blob(model))
    if not mt:
        return 0.0
    inter = len(pt & mt)
    union = len(pt | mt)
    return inter / union if union else 0.0


_HELPDESK_INTENT_RE = re.compile(
    r"(?i)\b("
    r"helpdesk|support\s+(?:desk|ticket)|IT\s+support|"
    r"slack\s+screenshots?|internal\s+helpdesk|IT\s+ticket"
    r")\b"
)
_WANT_TICKETS_RE = re.compile(r"(?i)\bi want tickets?\b")


def helpdesk_ticket_intent(prompt: str) -> bool:
    text = prompt or ""
    if has_positive_match(_HELPDESK_INTENT_RE, text):
        return True
    return has_positive_match(_WANT_TICKETS_RE, text)


def pack_conflicts_with_brief(
    prompt: str,
    pack_id: str,
    pack: dict[str, Any],
) -> tuple[bool, list[str]]:
    """True when operator brief out-of-scope / intent forbids this vertical pack."""
    from app.ai_operator_brief import build_operator_brief

    notes: list[str] = []
    brief = build_operator_brief(prompt)
    oos_blob = " ".join(str(x) for x in (brief.out_of_scope or [])).lower()
    pack_tags = {str(t).lower() for t in (pack.get("tags") or [])}
    template_ids = {
        str(m.get("model") or "")
        for m in (pack.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    }

    if helpdesk_ticket_intent(prompt) and pack_id != "helpdesk_tickets":
        notes.append(
            f"brief conflicts: helpdesk/ticket intent — reject vertical pack {pack_id!r}"
        )
        return True, notes

    if pack_id == "project_tracker":
        if "project" in oos_blob or re.search(r"(?i)clone\s+project\.task", prompt or ""):
            notes.append("brief conflicts: project out of scope vs project_tracker pack")
            return True, notes
        if "timesheet" in oos_blob or re.search(
            r"(?i)second\s+timesheet", prompt or ""
        ):
            notes.append("brief conflicts: timesheet out of scope vs project_tracker pack")
            return True, notes

    if "project" in oos_blob and pack_tags & {
        "project",
        "project management",
        "milestone",
        "pm",
        "timesheet",
        "time entry",
    }:
        notes.append(f"brief conflicts: project/timesheet out of scope vs {pack_id!r}")
        return True, notes

    if "project" in oos_blob and template_ids & {
        "x_project",
        "x_task",
        "x_milestone",
        "x_time_entry",
        "x_team_member",
    }:
        notes.append(
            f"brief conflicts: PM template models vs stated project out-of-scope ({pack_id})"
        )
        return True, notes

    if re.search(r"(?i)clone\s+project\.task", prompt or "") and template_ids & {
        "x_project",
        "x_task",
    }:
        notes.append(f"brief conflicts: do not clone project.task vs {pack_id!r}")
        return True, notes

    if "itsm" in oos_blob or re.search(
        r"(?i)not\s+selling\s+this\s+as\s+ITSM", prompt or ""
    ):
        if pack_id in {"project_tracker"} or pack_tags & {"project management", "pm"}:
            notes.append(f"brief conflicts: not ITSM / not PM vs {pack_id!r}")
            return True, notes

    return False, notes


def rank_domain_packs(prompt: str) -> list[tuple[str, float]]:
    """All curated packs scored against the prompt (high → low)."""
    from app.ai_domain_packs import _PACK_FACTORIES, score_domain_pack

    ranked: list[tuple[str, float]] = []
    for pack_id, factory, _pattern in _PACK_FACTORIES:
        ranked.append((pack_id, score_domain_pack(prompt, factory())))
    ranked.sort(key=lambda row: (-row[1], row[0]))
    return ranked


def should_apply_domain_pack(
    prompt: str,
    pack_id: str,
    pack: dict[str, Any],
    *,
    retrieval_score: float = 0.0,
    retrieval_method: str = "",
) -> tuple[bool, list[str]]:
    """Whether merging/applying a curated pack is coherent with the prompt."""
    from app.ai_domain_packs import score_domain_pack

    notes: list[str] = []
    conflicts, conflict_notes = pack_conflicts_with_brief(prompt, pack_id, pack)
    if conflicts:
        notes.extend(conflict_notes)
        return False, notes
    jaccard = score_domain_pack(prompt, pack) if pack else 0.0
    ranked = rank_domain_packs(prompt)
    best_id, best_score = ranked[0] if ranked else ("", 0.0)
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    min_j = (
        PACK_MERGE_MIN_JACCARD_REGEX
        if retrieval_method == "regex"
        else PACK_MERGE_MIN_JACCARD
    )

    # Regex is the high-precision signal (auto-hire, hospital management).
    # Short prompts score ~0.03–0.05 Jaccard against large pack vocabs, and
    # shared words ("booking") inflate the wrong vertical. Trust the pattern.
    if retrieval_method == "regex":
        return True, notes

    if pack_id and best_id and pack_id != best_id and best_score > jaccard + 0.04:
        notes.append(
            f"domain coherence: rejected pack {pack_id!r} — "
            f"competing pack {best_id!r} scores {best_score:.2f} vs {jaccard:.2f}"
        )
        return False, notes

    if (
        retrieval_method != "regex"
        and best_score < PACK_AMBIGUOUS_TOP_SCORE
        and best_score - second_score < PACK_MERGE_MIN_MARGIN
        and second_score > 0.0
    ):
        notes.append(
            "domain coherence: ambiguous pack fit — "
            f"top={best_id}@{best_score:.2f}, runner-up@{second_score:.2f}"
        )
        return False, notes

    if jaccard < min_j and retrieval_score < 0.35:
        notes.append(
            f"domain coherence: weak pack fit for {pack_id!r} "
            f"(Jaccard={jaccard:.2f}, retrieval={retrieval_score:.2f})"
        )
        return False, notes

    # Embedding-only hits (shared words like task/time/project) must not beat brief intent.
    if retrieval_method in {"embedding", "embedding_weak"} and jaccard < min_j:
        notes.append(
            f"domain coherence: embedding {pack_id!r} rejected — "
            f"Jaccard={jaccard:.2f} below {min_j:.2f}"
        )
        return False, notes

    return True, notes


def model_is_incoherent_with_prompt(
    model: dict[str, Any],
    prompt: str,
    *,
    prompt_industries: set[str] | None = None,
    pack_template_ids: set[str] | None = None,
    active_pack_id: str = "",
) -> bool:
    """True when a custom model is high-confidence cross-vertical pollution."""
    mid = str(model.get("model") or "")
    if not mid.startswith("x_"):
        return False
    if pack_template_ids and mid in pack_template_ids:
        return False

    allowed = set(prompt_industries or infer_prompt_industries(prompt))
    allowed -= {"generic_ops"}
    if active_pack_id:
        allowed.add(active_pack_id)
    if not allowed:
        return score_model_prompt_alignment(model, prompt) < MODEL_ALIGN_MIN

    mid_tokens = _tokenize(mid.replace("x_", "").replace("_", " "))
    for vertical in industry_cluster_keywords():
        if vertical in allowed or vertical == "generic_ops":
            continue
        distinctive = {t for t in _distinctive_cluster_tokens(vertical) if len(t) >= 5}
        if not distinctive:
            continue
        if mid_tokens & distinctive:
            return True
        if any(token in mid for token in distinctive if len(token) >= 6):
            return True
    return False


def list_incoherent_models(
    draft: dict[str, Any],
    prompt: str,
    *,
    pack: dict[str, Any] | None = None,
) -> list[str]:
    """Custom models that fail prompt/industry coherence."""
    from app.ai_domain_packs import pack_allowed_model_ids

    prompt_industries = infer_prompt_industries(prompt)
    template_ids: set[str] = set()
    pack_id = str(draft.get("domain_pack") or "")
    if pack:
        template_ids = pack_allowed_model_ids(pack)

    out: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        if model_is_incoherent_with_prompt(
            model,
            prompt,
            prompt_industries=prompt_industries,
            pack_template_ids=template_ids,
            active_pack_id=pack_id,
        ):
            out.append(mid)
    return sorted(out)


def prune_incoherent_models(
    draft: dict[str, Any],
    prompt: str,
    *,
    pack: dict[str, Any] | None = None,
    purge_fn: Any | None = None,
) -> list[str]:
    """Remove cross-industry / low-alignment models and reuse forbid_parallel stubs."""
    notes: list[str] = []
    pack_id = str(draft.get("domain_pack") or "")
    if pack is None and pack_id:
        from app.ai_domain_packs import load_domain_pack

        pack = load_domain_pack(pack_id)

    forbid: list[str] = []
    if pack:
        for row in pack.get("reuse_stock") or []:
            if isinstance(row, dict):
                forbid.extend(str(x) for x in (row.get("forbid_parallel") or []))

    from app.ai_reuse_planner import collapse_forbidden_parallel_models

    notes.extend(collapse_forbidden_parallel_models(draft, forbid))

    from app.ai_domain_packs import pack_allowed_model_ids

    template_ids = pack_allowed_model_ids(pack) if pack else set()
    pack_id = str(draft.get("domain_pack") or "")
    by_id = {
        str(m.get("model") or ""): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }

    removed: set[str] = set()
    for mid, model in by_id.items():
        if mid in template_ids:
            continue
        if mid.endswith("_line"):
            parent = mid[: -len("_line")]
            if parent in template_ids:
                continue
            if parent in by_id and parent not in removed:
                if not model_is_incoherent_with_prompt(
                    model,
                    prompt,
                    pack_template_ids=template_ids,
                    active_pack_id=pack_id,
                ):
                    continue
        if model_is_incoherent_with_prompt(
            model,
            prompt,
            pack_template_ids=template_ids,
            active_pack_id=pack_id,
        ):
            removed.add(mid)

    if not removed:
        return notes

    if purge_fn is None:
        from app.ai_domain_packs import _purge_draft_artifacts_for_models

        purge_fn = _purge_draft_artifacts_for_models

    purge_fn(draft, removed)
    notes.append(
        f"domain coherence: removed incoherent models {', '.join(sorted(removed))}"
    )
    return notes


__all__ = [
    "industry_cluster_keywords",
    "infer_prompt_industries",
    "infer_model_industries",
    "score_model_prompt_alignment",
    "rank_domain_packs",
    "should_apply_domain_pack",
    "model_is_incoherent_with_prompt",
    "list_incoherent_models",
    "prune_incoherent_models",
]

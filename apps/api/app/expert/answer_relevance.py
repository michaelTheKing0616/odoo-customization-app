"""Detect when LLM output does not answer the current question."""

from __future__ import annotations

import re

from app.expert.stack_inference import is_setup_stack_question

_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "in",
        "on",
        "for",
        "of",
        "is",
        "it",
        "this",
        "that",
        "what",
        "how",
        "when",
        "where",
        "does",
        "do",
        "can",
        "you",
        "your",
        "with",
        "without",
        "from",
        "into",
        "use",
        "using",
        "odoo",
        "community",
    }
)

# Copied from the old prompt example — if the model regurgitates this, reject.
_EXAMPLE_ECHO_RE = re.compile(
    r"(?i)install\s+\*\*contacts\*\*\s+for\s+students|use\s+\*\*crm\*\*\s+for\s+admissions"
)

# Topic leakage: access-control prose on non-access questions.
_ACCESS_LEAK_RE = re.compile(
    r"(?i)\bir\.model\.access\b.*\bir\.rule\b|accesserror while writing to x_matter"
)

# Vertical topic markers — reject answers dominated by the wrong industry.
_WRONG_VERTICAL_ANSWER_MARKERS: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...] = (
    (
        re.compile(r"(?i)\b(oil|gas|petroleum|upstream|midstream|downstream|oilfield)\b"),
        re.compile(
            r"(?i)\b(real estate|property rental|x_real_estate|tenant portal|"
            r"hotel room|law firm matter|library member|x_lib_)\b"
        ),
    ),
    (
        re.compile(r"(?i)\b(library|isbn|book loan|x_lib_)\b"),
        re.compile(r"(?i)\b(real estate|x_real_estate|hotel room|oil and gas|x_og_)\b"),
    ),
    (
        re.compile(r"(?i)\b(real estate|property rental|tenant)\b"),
        re.compile(r"(?i)\b(oil and gas|x_og_|library management|x_lib_)\b"),
    ),
)


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z][a-z0-9_]{2,}", text.lower())
        if t not in _STOP and len(t) > 2
    }


def answer_matches_question(question: str, answer: str) -> bool:
    """Return False when the answer is clearly off-topic or echoing prompt junk."""
    q = (question or "").strip()
    a = (answer or "").strip()
    if not q or not a:
        return False

    if _EXAMPLE_ECHO_RE.search(a):
        return False

    q_tok = _tokens(q)
    a_tok = _tokens(a)
    if not q_tok:
        return True

    overlap = len(q_tok & a_tok) / max(len(q_tok), 1)

    # Access answer on non-access question (common conversation/prompt leak).
    if _ACCESS_LEAK_RE.search(a) and not re.search(
        r"(?i)\b(accesserror|ir\.model\.access|record rule|permission)\b", q
    ):
        return False

    for q_pat, wrong_pat in _WRONG_VERTICAL_ANSWER_MARKERS:
        if q_pat.search(q) and wrong_pat.search(a):
            return False

    # Setup answers must not invent a specific unrelated vertical playbook.
    if re.search(
        r"(?i)\b(what do i need|which modules|setup|set up|build an odoo)\b",
        q,
    ) and re.search(
        r"(?i)\b(for a law firm|for a hotel|real estate management|library management system)\b",
        a,
    ):
        if not re.search(
            r"(?i)\b(law firm|hotel|real estate|library)\b",
            q,
        ):
            return False

    # Require at least one “anchor” token from the question in the answer.
    anchors = {t for t in q_tok if len(t) >= 5 or "_" in t}
    if anchors and not (anchors & a_tok):
        # Allow generic Odoo terms if strong overlap otherwise.
        if overlap < 0.12:
            return False

    if overlap < 0.08:
        return False

    return True


def conversation_is_on_topic(question: str, conversation: list[dict[str, str]] | None) -> bool:
    """Drop stale thread turns when the new question is a different topic."""
    if not conversation:
        return True
    if is_setup_stack_question(question or ""):
        return False
    last_user = ""
    for turn in reversed(conversation):
        if str(turn.get("role") or "").strip().lower() == "user":
            last_user = str(turn.get("content") or "").strip()
            break
    if not last_user:
        return True
    q_tok = _tokens(question)
    u_tok = _tokens(last_user)
    if not q_tok or not u_tok:
        return True
    overlap = len(q_tok & u_tok) / max(len(q_tok | u_tok), 1)
    return overlap >= 0.12

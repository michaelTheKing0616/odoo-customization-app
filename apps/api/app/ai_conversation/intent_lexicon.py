"""Production NL lexicon for ModuleSpec refine.

Deterministic intent is matched anywhere in the utterance (not only at the start),
covers informal verbs and common typos, and strips chat fluff so field labels remain.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Precedence: first matching family wins. Restore beats add ("add it back").
# Require is checked after add so "add a required due date" stays add.
VERB_ORDER = (
    "restore",
    "undo",
    "remove",
    "hide",
    "show",
    "rename",
    "approval",
    "optional",
    "place",
    "add",
    "require",
)

_FLUFF_PREFIX = re.compile(
    r"(?i)^(?:please|pls|plz|pretty\s+please|thanks|thx|thank\s+you|"
    r"hey|hi|hello|ok(?:ay)?|so|basically|actually|wait|"
    r"um+|uh+|like|just|kinda|kind\s+of|maybe|perhaps|"
    r"can\s+you(?:\s+please)?|could\s+you(?:\s+please)?|would\s+you|"
    r"we\s+(?:should|need\s+to|wanna|want\s+to)|"
    r"i\s+(?:want\s+to|wanna|would\s+like\s+to|d\s+like\s+to|need\s+to)|"
    r"let['’]?s|kindly)\s+"
)
_FLUFF_SUFFIX = re.compile(
    r"(?i)\s+(?:please|pls|plz|thanks|thx|thank\s+you|for\s+me|"
    r"if\s+(?:possible|you\s+can)|asap|now|though)\s*[.!?]*$"
)
_TRAILING_PUNCT = re.compile(r"[.!?…]+$")

_PRONOUN = re.compile(
    r"(?i)^(?:it|that|this|them|those|these|"
    r"(?:the\s+)?(?:field|one|last\s+(?:one|field|thing)|same)|"
    r"that\s+one|this\s+one)$"
)

# Common operator typos — keep this allowlist small and high-precision.
_TYPOS: dict[str, str] = {
    "priorty": "priority",
    "priortiy": "priority",
    "prioriy": "priority",
    "pirority": "priority",
    "satatus": "status",
    "staus": "status",
    "statu": "status",
    "stauts": "status",
    "assest": "asset",
    "asest": "asset",
    "asste": "asset",
    "catagory": "category",
    "categroy": "category",
    "cateogry": "category",
    "discription": "description",
    "descption": "description",
    "descripion": "description",
    "referance": "reference",
    "refrence": "reference",
    "referrence": "reference",
    "requster": "requester",
    "requestor": "requester",
    "reqester": "requester",
    "contat": "contact",
    "cantact": "contact",
    "conatct": "contact",
    "requried": "required",
    "requied": "required",
    "manditory": "mandatory",
    "optionl": "optional",
    "remvoe": "remove",
    "reomve": "remove",
    "deelte": "delete",
    "delte": "delete",
    "restroe": "restore",
    "restaore": "restore",
    "hdie": "hide",
    "shwo": "show",
}

_CANON_VERBS: dict[str, tuple[str, ...]] = {
    "remove": (
        "remove",
        "delete",
        "drop",
        "strip",
        "omit",
        "exclude",
        "discard",
        "erase",
        "nuke",
        "yeet",
        "ditch",
        "scrap",
        "trash",
        "kill",
        "lose",
        "dump",
        "purge",
        "expunge",
        "clear",
        "wipe",
        "ax",
        "cut",
    ),
    "restore": (
        "restore",
        "undelete",
        "un-delete",
        "revert",
        "reinstate",
        "recover",
        "retrieve",
    ),
    "undo": ("undo", "oops", "whoops", "redo"),
    "hide": ("hide", "conceal", "collapse", "fold"),
    "show": ("show", "unhide", "reveal", "display", "uncollapse"),
    "place": ("place", "relocate"),
    "add": ("add", "create", "include", "insert", "introduce", "append", "put"),
    "rename": ("rename", "relabel", "retitle", "relable"),
    "require": ("require", "required", "mandatory"),
    "optional": ("optional", "unrequire"),
}

# Phrases matched with search() anywhere. Restore includes "add back" so it beats add.
_FAMILY_RES: dict[str, tuple[re.Pattern[str], ...]] = {
    "undo": (
        re.compile(r"(?i)\b(?:undo|oops|whoops|my\s+bad|scratch\s+that|never\s*mind)\b"),
        re.compile(r"(?i)\bi\s+didn['’]t\s+mean(?:\s+(?:that|it|to))?\b"),
        re.compile(r"(?i)\bwait,?\s*no\b"),
        re.compile(r"(?i)\bthat\s+was(?:n['’]t|\s+not)\s+(?:right|what\s+i\s+meant)\b"),
    ),
    "restore": (
        re.compile(
            r"(?i)\b(?:restore|undelete|un-?delete|reinstate|recover|retrieve|bring\s+back|"
            r"put\s+back|place\s+back|add\s+back|re-?add)\b"
        ),
        re.compile(r"(?i)\b(?:bring|put|place|add)\s+(?:it|that|them|this)?\s*back\b"),
        re.compile(r"(?i)\bput\s+(?:the\s+)?.{0,40}\s+back\b"),
    ),
    "remove": (
        re.compile(
            r"(?i)\b(?:remove|delete|drop|strip|omit|exclude|discard|erase|nuke|yeet|"
            r"ditch|scrap|trash|kill|lose|dump|purge|expunge|wipe|ax|cut)\b"
        ),
        re.compile(r"(?i)\b(?:take|rip|peel)\s+(?:it\s+)?off\b"),
        re.compile(r"(?i)\bget\s+rid(?:\s+of)?\b"),
        re.compile(r"(?i)\bdon['’]t\s+(?:need|want|show)\b"),
        re.compile(r"(?i)\bdo\s+not\s+(?:need|want)\b"),
        re.compile(r"(?i)\bno\s+(?:more|need\s+for)\b"),
        re.compile(r"(?i)\bno\s+longer\s+(?:need|want|show)\b"),
        re.compile(r"(?i)\bwithout\b"),
        re.compile(r"(?i)\b(?:rm|del)\b"),
        re.compile(r"(?i)\btake\s+(?:out|away)\b"),
        re.compile(r"(?i)\bget\s+(?:that|it|this)\s+(?:out|gone|off)\b"),
        re.compile(r"(?i)\bclear\s+(?:out\s+)?(?:the\s+)?"),
    ),
    "hide": (re.compile(r"(?i)\b(?:hide|conceal|collapse|fold)\b"),),
    "show": (re.compile(r"(?i)\b(?:show|unhide|un-hide|reveal|display|uncollapse)\b"),),
    "rename": (
        re.compile(r"(?i)\b(?:rename|relabel|retitle|relable)\b"),
        re.compile(r"(?i)\bcall\s+(?:it|this|that)\b"),
        re.compile(r"(?i)\bchange\s+(?:the\s+)?(?:label|name|title)\b"),
    ),
    "approval": (
        re.compile(r"(?i)\bapproval(?:\s+flow|\s+workflow)?\b"),
        re.compile(r"(?i)\b(?:manager|needs?)\s+approv"),
        re.compile(r"(?i)\b(?:submit|approve)\s+(?:and|or)\s+(?:approve|refuse)\b"),
    ),
    "optional": (
        re.compile(r"(?i)\b(?:optional|not\s+required|un-?require|make\s+optional)\b"),
    ),
    "place": (
        re.compile(
            r"(?i)\b(?:put|place|move)\s+(?!back\b)(?:the\s+)?.{0,48}?\s+"
            r"(?:next\s+to|beside|after|under|in(?:to)?|on(?:to)?)\s+"
        ),
    ),
    "add": (
        re.compile(
            r"(?i)\b(?:add|create|include|insert|introduce|append|new\s+field)\b"
        ),
    ),
    "require": (
        re.compile(
            r"(?i)\b(?:make|set|mark)\s+(?:the\s+)?.{0,40}?\s+(?:field\s+)?(?:required|mandatory)\b"
        ),
        re.compile(r"(?i)\b(?:should\s+be|must\s+be|needs?\s+to\s+be)\s+required\b"),
        re.compile(r"(?i)\b(?:must\s+have|make\s+required|set\s+required)\b"),
        re.compile(r"(?i)\b(?:required|mandatory)\b"),
    ),
}

# Clause onsets for compound prompts. Weaker adjectives (bare "required")
# must not split "add a required due date".
_CLAUSE_ONSET_RES: dict[str, tuple[re.Pattern[str], ...]] = {
    "undo": _FAMILY_RES["undo"],
    "restore": _FAMILY_RES["restore"],
    "remove": _FAMILY_RES["remove"],
    "hide": _FAMILY_RES["hide"],
    "show": _FAMILY_RES["show"],
    "rename": _FAMILY_RES["rename"],
    "approval": _FAMILY_RES["approval"],
    "add": _FAMILY_RES["add"],
    "optional": (
        re.compile(r"(?i)\b(?:make|set|mark)\s+(?:the\s+)?.{0,40}?\s+(?:field\s+)?optional\b"),
        re.compile(r"(?i)\b(?:not\s+required|un-?require)\b"),
    ),
    "place": (
        re.compile(
            r"(?i)\b(?:put|place|move)\s+(?!back\b)(?:the\s+)?.{0,48}?\s+"
            r"(?:next\s+to|beside|after|under|in(?:to)?|on(?:to)?)\s+"
        ),
    ),
    "require": (
        re.compile(
            r"(?i)\b(?:make|set|mark)\s+(?:the\s+)?.{0,40}?\s+(?:field\s+)?(?:required|mandatory)\b"
        ),
        re.compile(r"(?i)\b(?:should\s+be|must\s+be|needs?\s+to\s+be)\s+required\b"),
        re.compile(r"(?i)\b(?:must\s+have|make\s+required|set\s+required)\b"),
    ),
}

_TRAIL_CONJ = re.compile(r"(?i)[\s,;]*(?:\band\b|\bthen\b|\balso\b|\bplus\b)\s*$")

_RENAME_CAPTURE = re.compile(
    r"(?i)(?:rename|relabel|retitle|call(?:\s+it)?|change(?:\s+the)?(?:\s+label|\s+name)?)\s+"
    r"(?:the\s+)?(.+?)\s+(?:to|as)\s+(.+)$"
)
_REQUIRE_CAPTURE = re.compile(
    r"(?i)(?:make|set|mark)\s+(?:the\s+)?(.+?)\s+(?:field\s+)?(?:required|mandatory)$"
)
_OPTIONAL_CAPTURE = re.compile(
    r"(?i)(?:make|set|mark)\s+(?:the\s+)?(.+?)\s+(?:field\s+)?optional$"
)
_PLACE_CAPTURE = re.compile(
    r"(?i)\b(?:put|place|move)\s+(?:the\s+)?(.+?)\s+"
    r"(?:next\s+to|beside|after|under|in(?:to)?|on(?:to)?)\s+"
    r"(?:the\s+|a\s+|its\s+own\s+)?(.+)$"
)
_FROM_MODEL = re.compile(
    r"(?i)\s+(?:from|on|to|onto|off)\s+(?:the\s+)?(.+)$"
)

_VERB_STRIP: dict[str, re.Pattern[str]] = {
    "restore": re.compile(
        r"(?i)\b(?:restore|undelete|un-?delete|reinstate|recover|retrieve|"
        r"bring\s+back|put\s+back|place\s+back|add\s+back|re-?add|"
        r"bring|put|place|back|it|that|them|this)\b"
    ),
    "undo": re.compile(
        r"(?i)\b(?:undo|oops|whoops|my\s+bad|scratch\s+that|never\s*mind|"
        r"wait|no|that|was|right|meant|didn['’]t|mean|it)\b"
    ),
    "remove": re.compile(
        r"(?i)\b(?:remove|delete|drop|strip|omit|exclude|discard|erase|nuke|yeet|"
        r"ditch|scrap|trash|kill|lose|dump|purge|expunge|wipe|ax|cut|"
        r"take|rip|peel|off|get|rid|of|out|away|gone|without|rm|del|"
        r"don['’]t|do\s+not|need|want|show|no|more|longer|clear|"
        r"i|we|you)\b"
    ),
    "hide": re.compile(r"(?i)\b(?:hide|conceal|collapse|fold)\b"),
    "show": re.compile(r"(?i)\b(?:show|unhide|un-hide|reveal|display|uncollapse)\b"),
    "place": re.compile(
        r"(?i)\b(?:put|place|move|next|to|beside|after|under|in|into|on|onto|"
        r"the|a|vendor|customer|partner|dates?|journal|other|info|tab|field)\b"
    ),
    "add": re.compile(
        r"(?i)\b(?:add|create|include|insert|introduce|append|put|new|field|"
        r"a|an|the|required|please)\b"
    ),
    "require": re.compile(
        r"(?i)\b(?:make|set|mark|the|field|required|mandatory|should|must|be|"
        r"needs?|to|have)\b"
    ),
    "optional": re.compile(
        r"(?i)\b(?:make|set|mark|the|field|optional|not|required|un-?require)\b"
    ),
    "rename": re.compile(
        r"(?i)\b(?:rename|relabel|retitle|call|it|change|the|label|name|title)\b"
    ),
    "approval": re.compile(
        r"(?i)\b(?:add|enable|include|put|set\s*up|setup|an?|the|manager|"
        r"approval|flow|workflow)\b"
    ),
}


def similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def strip_chat_fluff(text: str) -> str:
    out = (text or "").strip()
    for _ in range(4):
        nxt = _FLUFF_PREFIX.sub("", out, count=1).strip()
        if nxt == out:
            break
        out = nxt
    out = _FLUFF_SUFFIX.sub("", out).strip()
    return _TRAILING_PUNCT.sub("", out).strip()


def fix_typos(text: str) -> str:
    parts = re.split(r"([^a-zA-Z0-9]+)", text or "")
    out: list[str] = []
    for part in parts:
        key = part.lower()
        out.append(_TYPOS.get(key, part) if part.isalpha() else part)
    return "".join(out)


def is_pronoun_remainder(text: str) -> bool:
    n = re.sub(r"\s+", " ", (text or "").strip().lower())
    n = re.sub(r"[.!?]+$", "", n)
    if not n:
        return True
    return bool(_PRONOUN.match(n))


def split_field_list(remainder: str) -> list[str]:
    """Split 'priority and category' / 'priority, category, and contact'."""
    raw = (remainder or "").strip()
    if not raw:
        return []
    parts = re.split(r"(?i)\s*(?:,|&|\band\b|\bthen\b|\balso\b|\bplus\b)\s*", raw)
    cleaned: list[str] = []
    skip = {"the", "a", "an", "field", "fields", "both", "all", "and", "then", "also", "plus"}
    for part in parts:
        item = re.sub(r"(?i)\s+field$", "", part).strip(" .")
        if item and item.lower() not in skip:
            cleaned.append(item)
    return cleaned or ([raw] if raw else [])


def _fuzzy_verb_token(token: str) -> str | None:
    if len(token) < 4:
        return None
    best_verb = ""
    best = 0.0
    for verb, words in _CANON_VERBS.items():
        for word in words:
            ratio = similar(token, word)
            if ratio > best:
                best = ratio
                best_verb = verb
    return best_verb if best >= 0.82 else None


def extract_remainder(text: str, verb: str) -> str:
    stripper = _VERB_STRIP.get(verb)
    body = text or ""
    if stripper:
        body = stripper.sub(" ", body)
    body = re.sub(r"(?i)\s+field$", "", body)
    body = re.sub(r"\s+", " ", body).strip(" .,-")
    return body


def _structured_intent(raw: str) -> tuple[str, str, str, str] | None:
    """Return (verb, remainder, model_hint, extra) for high-precision captures."""
    place = _PLACE_CAPTURE.search(raw)
    if place:
        from app.ai_form_slots import slot_from_location

        slot = slot_from_location(place.group(2))
        if slot:
            return "place", place.group(1).strip(), "", slot
    rename = _RENAME_CAPTURE.search(raw)
    if rename:
        return "rename", rename.group(1).strip(), "", rename.group(2).strip()
    require = _REQUIRE_CAPTURE.search(raw)
    if require:
        return "require", require.group(1).strip(), "", ""
    optional = _OPTIONAL_CAPTURE.search(raw)
    if optional:
        return "optional", optional.group(1).strip(), "", ""
    return None


def _verb_spans(raw: str) -> list[tuple[int, int, str]]:
    """Non-overlapping command onsets, restore/add-back winning over add."""
    cands: list[tuple[int, int, str, int]] = []
    for pri, verb in enumerate(VERB_ORDER):
        for pat in _CLAUSE_ONSET_RES.get(verb, ()):
            for match in pat.finditer(raw):
                cands.append((match.start(), match.end(), verb, pri))
    if not cands:
        return []
    cands.sort(key=lambda row: (row[0], row[3], -(row[1] - row[0])))
    picked: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, verb, _pri in cands:
        if start < last_end:
            continue
        picked.append((start, end, verb))
        last_end = end
    return picked


def split_instruction_clauses(text: str) -> list[str]:
    """Split 'remove Extra and restore Asset Tag' without splitting field lists."""
    raw = (text or "").strip()
    if not raw:
        return []
    spans = _verb_spans(raw)
    if len(spans) <= 1:
        return [raw]
    clauses: list[str] = []
    prev = 0
    for start, _end, _verb in spans[1:]:
        chunk = _TRAIL_CONJ.sub("", raw[prev:start]).strip(" ,;.")
        if chunk:
            clauses.append(chunk)
        prev = start
    tail = raw[prev:].strip(" ,;.")
    if tail:
        clauses.append(tail)
    return clauses or [raw]


def _classify_one(raw: str) -> tuple[str, str, str, str] | None:
    structured = _structured_intent(raw)
    if structured:
        verb, remainder, model_hint, extra = structured
        model_hint, remainder = _split_model_hint(remainder, model_hint)
        remainder = _TRAIL_CONJ.sub("", remainder).strip()
        return verb, remainder, model_hint, extra

    hits: list[str] = []
    for verb in VERB_ORDER:
        for pat in _FAMILY_RES.get(verb, ()):
            if pat.search(raw):
                hits.append(verb)
                break
    if not hits:
        for tok in re.findall(r"[a-zA-Z]+", raw.lower()):
            guessed = _fuzzy_verb_token(_TYPOS.get(tok, tok))
            if guessed and guessed not in hits:
                hits.append(guessed)
    if not hits:
        return None

    verb = hits[0]
    if verb == "require" and "add" in hits:
        verb = "add"
    remainder = extract_remainder(raw, verb)
    remainder = _TRAIL_CONJ.sub("", remainder).strip()
    extra = ""
    if verb == "rename":
        match = re.search(r"(?i)\b(?:to|as)\s+(.+)$", remainder)
        if match:
            extra = match.group(1).strip()
            remainder = remainder[: match.start()].strip()
    model_hint = ""
    model_hint, remainder = _split_model_hint(remainder, model_hint)
    remainder = _TRAIL_CONJ.sub("", remainder).strip()
    return verb, remainder, model_hint, extra


def classify_utterances(text: str) -> list[tuple[str, str, str, str]]:
    """Classify every command in a compound instruction, in order."""
    raw = fix_typos(strip_chat_fluff(text))
    if not raw:
        return []
    out: list[tuple[str, str, str, str]] = []
    for clause in split_instruction_clauses(raw):
        parsed = _classify_one(clause)
        if parsed:
            out.append(parsed)
    return out


def classify_utterance(text: str) -> tuple[str, str, str, str] | None:
    """First command in the utterance (tests / single-op helpers)."""
    parsed = classify_utterances(text)
    return parsed[0] if parsed else None


def _split_model_hint(remainder: str, model_hint: str) -> tuple[str, str]:
    if model_hint:
        return model_hint, remainder
    match = _FROM_MODEL.search(remainder)
    if match:
        hint = match.group(1).strip()
        body = remainder[: match.start()].strip()
        if body:
            return hint, body
    body = re.sub(r"(?i)\s+(?:on|from|to|onto|off|tickets?|form|app|model)$", "", remainder or "").strip()
    return "", body or remainder


__all__ = [
    "classify_utterance",
    "classify_utterances",
    "extract_remainder",
    "fix_typos",
    "is_pronoun_remainder",
    "similar",
    "split_field_list",
    "split_instruction_clauses",
    "strip_chat_fluff",
]

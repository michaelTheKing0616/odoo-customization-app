"""Metamorphic variants of a brief. Equivalent: paraphrase, irrelevant_insert. Changed: delete_requirement, negate."""
import re

_SWAPS = [(r"\bi need\b", "we want"), (r"\bneed to\b", "have to"), (r"\btrack\b", "keep a record of"),
          (r"\bremind\b", "send a reminder to"), (r"\bonly\b", "just"), (r"\beach\b", "every")]
IRRELEVANT = " By the way our office is painted blue and we open at 8am, that is not related to this."


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+|\n", text) if s.strip()]


def paraphrase(text):
    out = text
    for a, b in _SWAPS:
        out = re.sub(a, b, out, count=1, flags=re.I)
    return out


def irrelevant_insert(text):
    s = sentences(text)
    return " ".join(s[:1] + [IRRELEVANT.strip()] + s[1:])


def delete_requirement(text, idx=-1):
    s = [x for x in sentences(text) if len(x.split()) > 4]
    if len(s) < 3:
        return text, ""
    gone = s[idx]
    return text.replace(gone, "").strip(), gone


def negate(text, idx=-1):
    s = [x for x in sentences(text) if len(x.split()) > 4]
    target = s[idx] if s else ""
    return text.replace(target, "We do NOT want this: " + target), target


def variants(text):
    d, gone = delete_requirement(text)
    n, neg = negate(text)
    return [("paraphrase", paraphrase(text), "equivalent", ""), ("irrelevant_insert", irrelevant_insert(text), "equivalent", ""),
            ("delete_requirement", d, "changed", gone), ("negate", n, "changed", neg)]

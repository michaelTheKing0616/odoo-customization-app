"""Spec 11/15: zero technical names in the suite's default view, checked against the glossary.

Scans on-screen text in components/suite: JSX text and the visible props (placeholder, aria-label, title, label).
Show-code panels opt out by wrapping text in <code>.
"""
import re
from pathlib import Path

SUITE = Path(__file__).resolve().parents[2] / "web" / "src" / "components" / "suite"
BANNED = [r"\bir\.(cron|rule|model|access|attachment)\b", r"\bres\.(groups|partner|users)\b", r"\b(sale\.order|account\.move|crm\.lead)\b",
          r"\bcall_kw\b", r"\bJSON-RPC\b", r"\bRPC\b", r"\bxpath\b", r"\bxml ?id\b", r"\bdomain\b", r"\bdry[ _]run\b", r"\bl10n_", r"\btier-1\b",
          r"\bchecksum\b", r"\bmany2one\b", r"\bone2many\b", r"\bOops\b", r"\bplease\b", r"\binvalid\b", "\u2014"]
VISIBLE_PROP = re.compile(r'\b(?:placeholder|aria-label|title|label|purpose)="([^"]+)"')
JSX_TEXT = re.compile(r">([^<>{}();=?]*[A-Za-z][^<>{}();=?]*)<")
CODE = re.compile(r"<code>.*?</code>", re.S)


def _visible(src: str) -> list[str]:
    src = CODE.sub("", src)
    return [m.group(1) for m in VISIBLE_PROP.finditer(src)] + [m.group(1) for m in JSX_TEXT.finditer(src)]


def test_no_technical_names_on_screen():
    hits = []
    for f in sorted(SUITE.glob("*.tsx")):
        for text in _visible(f.read_text()):
            for pat in BANNED:
                if re.search(pat, text, re.I if pat[0] != "\\" or "RPC" not in pat else 0):
                    hits.append(f"{f.name}: {pat} in {text.strip()[:80]!r}")
    assert not hits, "\n".join(hits)

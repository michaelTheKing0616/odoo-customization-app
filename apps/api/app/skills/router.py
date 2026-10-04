"""Choose catalog skills for a phrase. A skill can only narrow the caller grant.

Recall and precision are not computed here. That eval stays open.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

from app.bots.grant import BotGrant
from app.skills.catalog import SkillPackage, all_skills, narrow_grant_ops

MAX_LOADED_SKILLS = 3
MAX_SKILL_TOKENS = 2500
# A SKILL.md past this size is already over the token cap. Do not read it all.
_MAX_SKILL_CHARS = 20_000

_TOKEN = re.compile(r"[a-z0-9]+")
_PYTHON_FENCE = re.compile(r"(?im)^[ \t]*(?:```+|~~~+)[ \t]*(?:python|py)\b")
_MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})


@dataclass(frozen=True, slots=True)
class SkillRoute:
    """Skills selected for one phrase.

    skill_ids is at most three catalog ids, best match first.
    grant is the caller grant after each loaded skill narrows it.
    refused lists catalog ids that matched and were not loaded.
    dropped lists later matches that lost to the cap of three.
    """

    skill_ids: tuple[str, ...]
    grant: BotGrant
    refused: tuple[str, ...]
    dropped: tuple[str, ...]


def skill_token_count(text: str) -> int:
    """Estimate tokens in skill markdown.

    Inputs: skill markdown text.
    Outputs: 13 tokens per 10 words. Empty text is 0. This is not a model
    tokenizer and it is not a recall or precision score.
    Side effects: none.
    """
    words = len(text.split())
    if words == 0:
        return 0
    return (words * 13) // 10


def match_skill_ids(phrase: str) -> tuple[str, ...]:
    """Return catalog ids that share a word with the phrase, best first.

    Inputs: the caller phrase. The catalog is ``all_skills()``.
    Outputs: ids ordered by shared-word count, then id. No score is returned.
    Side effects: none. Does not read skill files and does not call a model.
    """
    needles = _tokens(phrase)
    if not needles:
        return ()
    ranked: list[tuple[int, str]] = []
    for package in all_skills():
        hay = _tokens(f"{package.skill_id} {package.summary}")
        score = len(needles & hay)
        if score:
            ranked.append((score, package.skill_id))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return tuple(skill_id for _, skill_id in ranked)


def route_skills(
    phrase: str,
    grant: BotGrant,
    *,
    packages_root: Path | None = None,
) -> SkillRoute:
    """Load at most three catalog skills and narrow the caller grant.

    Inputs: the phrase, the caller grant, and an optional directory of skill
    packages. Ids always come from the catalog.
    Outputs: the loaded ids, the intersected grant, refused ids, and ids
    dropped because a fourth match does not load.
    Side effects: reads ``SKILL.md`` and sibling names under ``packages_root``
    when that directory is set. Does not write files, call a model, or widen
    the grant.
    """
    by_id = {package.skill_id: package for package in all_skills()}
    refused: list[str] = []
    eligible: list[SkillPackage] = []
    for skill_id in match_skill_ids(phrase):
        package = by_id[skill_id]
        if _refusal(package, packages_root):
            refused.append(skill_id)
            continue
        eligible.append(package)
    loaded = tuple(eligible[:MAX_LOADED_SKILLS])
    dropped = tuple(package.skill_id for package in eligible[MAX_LOADED_SKILLS:])
    return SkillRoute(
        skill_ids=tuple(package.skill_id for package in loaded),
        grant=_narrow(grant, loaded),
        refused=tuple(refused),
        dropped=dropped,
    )


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN.findall(text.lower()) if len(token) >= 3}


def _narrow(grant: BotGrant, loaded: tuple[SkillPackage, ...]) -> BotGrant:
    """Intersect the caller grant with each loaded skill. Never widen it.

    Inputs: the caller grant and the skills that will load.
    Outputs: the same grant when nothing loaded, otherwise a grant whose ops
    are the running intersection. Risk, autonomy, and apps stay the caller's.
    Side effects: none.
    """
    if not loaded:
        return grant
    narrowed = grant.ops_allowed
    for package in loaded:
        narrowed = narrow_grant_ops(narrowed, package.ops_allowed)
    if not narrowed <= grant.ops_allowed:
        narrowed = narrowed & grant.ops_allowed
    return replace(grant, ops_allowed=narrowed)


def _refusal(package: SkillPackage, packages_root: Path | None) -> str | None:
    """Return a refusal reason, or None when the package may load.

    A fenced Python block in SKILL.md refuses the skill. A file other than
    SKILL.md and markdown refuses it. SKILL.md over 2500 estimated tokens
    refuses it.
    Inputs: one catalog package and the optional package root.
    Outputs: ``python_fence``, ``executable_file``, ``token_cap``, or None.
    Side effects: reads the package directory when ``packages_root`` is set.
    """
    text = package.markdown()
    if packages_root is not None:
        folder = packages_root / package.skill_id
        if folder.is_dir():
            if _foreign_files(folder):
                return "executable_file"
            skill_md = folder / "SKILL.md"
            if skill_md.is_file():
                loaded = _read_skill_md(skill_md)
                if loaded is None:
                    return "token_cap"
                text = loaded
    if _PYTHON_FENCE.search(text):
        return "python_fence"
    if skill_token_count(text) > MAX_SKILL_TOKENS:
        return "token_cap"
    return None


def _foreign_files(folder: Path) -> bool:
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if path.name == "SKILL.md":
            continue
        if path.suffix.lower() in _MARKDOWN_SUFFIXES:
            continue
        return True
    return False


def _read_skill_md(path: Path) -> str | None:
    """Read SKILL.md when it is utf-8 and within the size cap.

    Inputs: path to SKILL.md.
    Outputs: the text, or None when the file is too large or not utf-8.
    Side effects: reads the file.
    """
    if path.stat().st_size > _MAX_SKILL_CHARS:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None

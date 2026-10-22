#!/usr/bin/env python3
"""T0 helper for the Orchestrator: list cards that can be dispatched now. Read-only.

A card is eligible when: Status is todo; its phase is in --phases; every `Depends on` card is done; its Gate is not an
unresolved A (the card body says "Gate: A"); none of its allow-list paths overlaps an open lock in STATE.md.
Usage: python3 docs/build-plan/tools/next_cards.py --phases 0[,1] [--limit 10]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1]
DEP_ID = re.compile(r"\b(?!DEC-)[A-Z][A-Z0-9]*(?:-[A-Z0-9.]+)+\b")


def field(body: str, name: str) -> str:
    m = re.search(rf"^{re.escape(name)}:\s*(.*)$", body, re.M)
    return m.group(1).strip() if m else ""


def allow_list(body: str) -> list[str]:
    m = re.search(r"^File allow-list:\n((?:- .*\n)+)", body, re.M)
    return [ln[2:].split(" (")[0].strip() for ln in m.group(1).splitlines()] if m else []


def open_locks() -> list[str]:
    state = (PLAN / "STATE.md").read_text()
    sec = state.split("## File locks", 1)[-1].split("\n## ", 1)[0]
    paths = []
    for row in sec.splitlines():
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) >= 4 and cells[0] not in ("Lock", "---") and not set(cells[0]) <= {"-"}:
            paths += [p.strip(" `") for p in cells[3].split(",") if p.strip()]
    return paths


def overlaps(a: str, b: str) -> bool:
    return a.startswith(b) or b.startswith(a)


def main() -> int:
    args = sys.argv[1:]
    phases = {int(x) for x in args[args.index("--phases") + 1].split(",")} if "--phases" in args else {0}
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 10
    cards = {p.stem: p.read_text() for p in (PLAN / "cards").glob("phase-*/*.md")}
    status = {cid: (field(b, "Status").split() or ["todo"])[0].lower() for cid, b in cards.items()}
    locks = open_locks()
    rows = []
    for cid, body in sorted(cards.items(), key=lambda kv: (int(field(kv[1], "Phase") or 9), field(kv[1], "Priority"), kv[0])):
        if status[cid] != "todo" or int(field(body, "Phase") or 99) not in phases:
            continue
        deps = [d for d in DEP_ID.findall(field(body, "Depends on")) if d != cid]
        waiting = [d for d in deps if status.get(d) != "done"]
        gate = field(body, "Gate").split(" ")[0]
        locked = [p for p in allow_list(body) if any(overlaps(p, lk) for lk in locks)]
        if waiting or gate == "A" or locked:
            continue
        rows.append((cid, field(body, "Phase"), field(body, "Priority"), field(body, "Type"),
                     re.search(r"Worker: (\S+)", body).group(1), re.search(r"Budget: (\w+)", body).group(1)))
    print("| # | Card | Phase | Pri | Type | Tier | Budget |")
    print("|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows[:limit], 1):
        print(f"| {i} | {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")
    print(f"\n{len(rows)} eligible in phases {sorted(phases)}; {len(locks)} locked paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

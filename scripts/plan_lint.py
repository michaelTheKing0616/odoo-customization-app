#!/usr/bin/env python3
"""Lint the Ingenium build plan: ledger <-> card traceability and card required fields.

Usage:
    python3 scripts/plan_lint.py ledger            # G0: ledger structure + coverage report
    python3 scripts/plan_lint.py cards --phase 0   # G2: card files for one phase
    python3 scripts/plan_lint.py all               # GATE-E / release: every phase

Inputs:  docs/build-plan/ledger.csv, docs/build-plan/cards/phase-*/<ID>.md,
         docs/build-plan/phase_map.json (card-id prefix -> phase; optional until Stage 2).
Outputs: a summary on stdout; writes docs/build-plan/coverage/<mode>.md.
Exit code: 0 when clean, 1 when any error is found. No network, no database, read-only
except for the coverage report.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "build-plan"
LEDGER = PLAN / "ledger.csv"
CARDS = PLAN / "cards"
PHASE_MAP = PLAN / "phase_map.json"
COVERAGE_DIR = PLAN / "coverage"

COLUMNS = ["ID", "source_section", "one_line", "type", "priority",
           "status_label_today", "card_ids", "tope_decision"]
TYPES = {"build", "rebuild", "prove-live", "verify", "test", "docs", "decision",
         "ui-spec", "ui-build", "regression", "security", "invariant"}
PRIORITIES = {"P0", "P1", "P2", "P3", "INV"}
DOC_TARGETS = {"02_INVARIANTS", "06_TEST_STRATEGY", "07_UI_PROTOCOL", "FACTS",
               "CODE_MAP", "GATE-R"}
HOLD_STATUSES = {"SPEC-TEXT-NEEDED", "ITEMISE-AT-G2"}
DECISION_RE = re.compile(r"^(DEC-\d{3}|D\d+)$")

CARD_FIELDS = ["ID", "Title", "Phase", "Priority", "Type", "TOKEN CHARTER",
               "Ledger IDs", "Depends on", "Routing", "Context pack",
               "File allow-list", "Goal", "Steps", "Acceptance criteria",
               "Test plan", "Gate", "Evidence to log", "Rollback",
               "Definition of Done"]
CARD_STATUSES = {"todo", "in-progress", "blocked", "done"}
RISK_PATHS = ("write_gate", "dry_run_middleware", "dry_run_ledger", "protected_",
              "money", "auth", "tenan", "ir_access_shim", "alembic")
MAX_CARD_LINES = 150
BUDGET_FILE = PLAN / "budget.json"
BUDGET_CLASSES = set(json.loads(BUDGET_FILE.read_text())["classes"]) if BUDGET_FILE.exists() else set()


def tier_for_score(score: int) -> str:
    if score <= 2:
        return "L1"
    if score <= 5:
        return "L2"
    return "L3"


def load_ledger(errors: list[str]) -> list[dict[str, str]]:
    with LEDGER.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            errors.append(f"ledger columns {reader.fieldnames} != {COLUMNS}")
            return []
        rows = list(reader)
    seen: Counter[str] = Counter(r["ID"] for r in rows)
    for dup, count in seen.items():
        if count > 1:
            errors.append(f"duplicate ledger ID {dup} x{count}")
    for row in rows:
        rid = row["ID"]
        if row["type"] not in TYPES:
            errors.append(f"{rid}: bad type {row['type']!r}")
        if row["priority"] not in PRIORITIES:
            errors.append(f"{rid}: bad priority {row['priority']!r}")
        if not row["one_line"].strip() or not row["source_section"].strip():
            errors.append(f"{rid}: empty one_line or source_section")
        cards = split_ids(row["card_ids"])
        decision = row["tope_decision"].strip()
        if not cards and not decision:
            errors.append(f"{rid}: no card and no Tope decision (zero-loss rule 1)")
        if decision and not all(DECISION_RE.match(d) for d in split_ids(decision)):
            errors.append(f"{rid}: bad decision id {decision!r}")
    return rows


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def section_key(source: str) -> str:
    first = source.split(";")[0].strip()
    match = re.match(r"(§\d+(?:\.\d+)?|§4 P\d|§App\. [A-D]|FA|DESIGN_TOUCHES|MANIFEST|user brief|repo)", first)
    return match.group(1) if match else first.split(" ")[0]


def parse_card(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    current = None
    for line in path.read_text().splitlines():
        header = re.match(r"^(?:#+\s*|\*\*)?([A-Za-z][A-Za-z /\-]+?)(?:\*\*)?:\s*(.*)$", line)
        if header and header.group(1).strip() in CARD_FIELDS + ["Status", "Elite design notes", "Oracle tests"]:
            current = header.group(1).strip()
            fields[current] = header.group(2).strip()
        elif current:
            fields[current] += "\n" + line
    fields["_lines"] = str(len(path.read_text().splitlines()))
    return fields


def lint_card(path: Path, ledger_ids: set[str], errors: list[str]) -> list[str]:
    card = parse_card(path)
    cid = path.stem
    for name in CARD_FIELDS:
        if not card.get(name, "").strip():
            errors.append(f"{cid}: missing field {name!r}")
    if int(card["_lines"]) > MAX_CARD_LINES:
        errors.append(f"{cid}: {card['_lines']} lines > {MAX_CARD_LINES}; split it")
    status = card.get("Status", "todo").split()[0].lower() if card.get("Status") else "todo"
    if status not in CARD_STATUSES:
        errors.append(f"{cid}: status {status!r} not in {sorted(CARD_STATUSES)} (no 'partial')")
    acs = re.findall(r"^\s*-?\s*AC\d+", card.get("Acceptance criteria", ""), re.M)
    if not acs:
        errors.append(f"{cid}: no testable AC lines (AC1, AC2 ...)")
    charter = card.get("TOKEN CHARTER", "")
    budget_match = re.search(r"Budget:\s*(XS|S|M|L|XL)\b", charter)
    if "Stop at 80%" not in charter or not budget_match:
        errors.append(f"{cid}: TOKEN CHARTER line lacks 'Budget: <class>' + 'Stop at 80%'")
    elif budget_match.group(1) not in BUDGET_CLASSES:
        errors.append(f"{cid}: budget class {budget_match.group(1)} not in budget.json")
    routing = card.get("Routing", "")
    score_match = re.search(r"Score:\s*(\d+)", routing)
    worker_match = re.search(r"Worker:\s*(L[1-3]|E[12])", routing)
    if not score_match or not worker_match:
        errors.append(f"{cid}: Routing needs 'Worker: Lx' and 'Score: n'")
    else:
        score = int(score_match.group(1))
        worker = worker_match.group(1)
        if worker.startswith("E"):
            if not (budget_match and budget_match.group(1) == "XL"):
                errors.append(f"{cid}: E-tier Worker only on XL elite design cards; otherwise route to an L tier")
        elif worker != tier_for_score(score) and not re.search(r"de-escalat|pilot", routing, re.I):
            errors.append(f"{cid}: score {score} -> {tier_for_score(score)}, card says {worker}")
        if score >= 6:
            for name in ("Elite design notes", "Oracle tests"):
                if len(card.get(name, "").strip()) < 20:
                    errors.append(f"{cid}: score {score} >= 6 requires non-empty {name!r}")
    allow = card.get("File allow-list", "")
    allow_for_risk = re.sub(r"authori[sz]", "", allow)  # model authorizer is design quality, not sign-in auth
    if any(p in allow_for_risk for p in RISK_PATHS) and "Worker: L3" not in routing:
        errors.append(f"{cid}: allow-list touches a guarded path; Worker must be L3 (INV-14)")
    covered = split_ids(card.get("Ledger IDs", "").replace(",", ";"))
    for lid in covered:
        if lid not in ledger_ids:
            errors.append(f"{cid}: ledger ID {lid} not in ledger.csv")
    return covered


DEP_ID = re.compile(r"\b(?!DEC-)[A-Z][A-Z0-9]*(?:-[A-Z0-9.]+)+\b")


def lint_dependencies(cards: dict[str, Path], known: set[str], errors: list[str]) -> None:
    """Every `Depends on` ID is a card file or a planned card, and the card graph has no cycle."""
    graph = {cid: [d for d in DEP_ID.findall(parse_card(p).get("Depends on", "")) if d != cid]
             for cid, p in cards.items()}
    for cid, deps in graph.items():
        for dep in deps:
            if dep not in cards and dep not in known:
                errors.append(f"{cid}: depends on unknown card {dep}")
    state: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> None:
        if state.get(node) == 1:
            errors.append("dependency cycle: " + " -> ".join(path[path.index(node):] + [node]))
            return
        if state.get(node) == 2 or node not in graph:
            return
        state[node] = 1
        for dep in graph[node]:
            visit(dep, path + [node])
        state[node] = 2

    for cid in sorted(graph):
        visit(cid, [])


def phase_of(card_id: str, phase_map: dict[str, int]) -> int | None:
    best = None
    for prefix, phase in phase_map.items():
        if card_id.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, phase)
    return best[1] if best else None


def write_report(mode: str, lines: list[str]) -> Path:
    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)
    out = COVERAGE_DIR / f"{mode}.md"
    out.write_text("\n".join(lines) + "\n")
    return out


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "ledger"
    phase_filter = int(argv[argv.index("--phase") + 1]) if "--phase" in argv else None
    prefix_filter = argv[argv.index("--prefix") + 1] if "--prefix" in argv else ""
    errors: list[str] = []
    rows = load_ledger(errors)
    ledger_ids = {r["ID"] for r in rows}
    phase_map = json.loads(PHASE_MAP.read_text()) if PHASE_MAP.exists() else {}

    by_section: dict[str, Counter[str]] = defaultdict(Counter)
    planned_cards: set[str] = set()
    holds, wildcards, decisions = [], [], Counter()
    for row in rows:
        key = section_key(row["source_section"])
        cards = split_ids(row["card_ids"])
        by_section[key]["rows"] += 1
        by_section[key]["covered"] += 1 if (cards or row["tope_decision"]) else 0
        for card in cards:
            if card.endswith("*"):
                wildcards.append(f"{row['ID']} -> {card}")
            elif card not in DOC_TARGETS:
                planned_cards.add(card)
        if row["status_label_today"] in HOLD_STATUSES:
            holds.append(f"{row['ID']} ({row['status_label_today']})")
        for dec in split_ids(row["tope_decision"]):
            decisions[dec] += 1

    card_files = {p.stem: p for p in CARDS.glob("phase-*/*.md")}
    card_coverage: dict[str, list[str]] = {}
    if mode in ("cards", "all"):
        for cid, path in sorted(card_files.items()):
            phase = int(path.parent.name.split("-")[1])
            if (phase_filter is not None and phase != phase_filter) or not cid.startswith(prefix_filter):
                continue
            card_coverage[cid] = lint_card(path, ledger_ids, errors)
        for card in sorted(planned_cards):
            if not card.startswith(prefix_filter):
                continue
            phase = phase_of(card, phase_map)
            if phase is None:
                errors.append(f"planned card {card}: no prefix in phase_map.json")
            elif (phase_filter is None or phase == phase_filter) and card not in card_files:
                errors.append(f"planned card {card} (phase {phase}) has no card file")
        lint_dependencies(card_files, planned_cards, errors)
        for row in rows:
            for card in split_ids(row["card_ids"]):
                if card in card_coverage and row["ID"] not in card_coverage[card]:
                    errors.append(f"{card}: does not list ledger ID {row['ID']} that points to it")

    total = sum(c["rows"] for c in by_section.values())
    uncovered = total - sum(c["covered"] for c in by_section.values())
    report = [f"# plan_lint coverage: {mode}" + (f" phase {phase_filter}" if phase_filter is not None else ""),
              "", f"Ledger rows: {total}. Uncovered: {uncovered}. Planned cards: {len(planned_cards)}. "
              f"Card files linted: {len(card_coverage)}. Decisions referenced: {len(decisions)}.", "",
              "| Source | Rows | Covered |", "|---|---|---|"]
    report += [f"| {k} | {v['rows']} | {v['covered']} |" for k, v in sorted(by_section.items())]
    report += ["", f"Holds to resolve before their phase G2: {len(holds)}"] + [f"- {h}" for h in holds]
    report += ["", f"Wildcard card refs (expand at G2): {len(wildcards)}"] + [f"- {w}" for w in wildcards]
    report += ["", f"Errors: {len(errors)}"] + [f"- {e}" for e in errors]
    name = mode if phase_filter is None else f"{mode}-phase-{phase_filter}"
    out = write_report(name + (f"-{prefix_filter.rstrip('-*')}" if prefix_filter else ""), report)
    print(f"rows={total} uncovered={uncovered} planned_cards={len(planned_cards)} "
          f"holds={len(holds)} wildcards={len(wildcards)} errors={len(errors)} -> {out.relative_to(ROOT)}")
    for err in errors[:20]:
        print("ERROR", err)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

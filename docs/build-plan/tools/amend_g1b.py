#!/usr/bin/env python3
"""G1B amendments (21 Oct): ledger rows for the App Studio Design Pack cards. Idempotent.

Side effects: rewrites docs/build-plan/ledger.csv in place and writes docs/build-plan/phase_map.json
(the AS- prefix only; Stage 2 extends it). Prints a one-line summary.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1]
LEDGER = PLAN / "ledger.csv"
rows = list(csv.DictReader(LEDGER.open()))
FIELDS = list(rows[0].keys())
by_id = {r["ID"]: r for r in rows}

NEW = [
    ("AS-RC1", "Pack §2 RC1; ai_studio.py L637-639; app_design.py L1504 L2697", "designer prompt + model budget + outline read the AI expansion as the owner's brief", "build", "P0", "Verified", "AS-SRC-BRIEF;AS-EXP-X0"),
    ("AS-RC4", "Pack §2 RC4", "18 env flags choose the App Studio pipeline; one typed profile instead, logged per session and per eval run", "build", "P1", "Verified", "AS-PROFILE"),
    ("AS-RC5", "Pack §2 RC5; llm_provider.py GeminiProvider", "Gemini generate_json discards format_schema: no constrained decoding in production", "build", "P1", "Verified", "AS-DECODE"),
    ("AS-RC6", "Pack §2 RC6; app_design.py L1561", "no total-function boundary: only LLMError/TimeoutError caught; None used as a meaning", "build", "P0", "Verified", "AS-TOTAL;AS-ROBUST-FUZZ"),
    ("AS-LEDGER", "Pack §4-§5", "Brief Ledger: verbatim-offset spans; entity roles; facts; rules; noise; unsure; validators L1-L8", "build", "P1", "Missing", "AS-LEDGER-SCHEMA;AS-LEDGER-CALL"),
    ("AS-COMPILE-ROW", "Pack §6.3", "deterministic Ledger -> AppDesign compiler; structure hash guards Polish", "build", "P1", "Missing", "AS-COMPILE"),
    ("AS-PROMOTE-ROW", "Pack §6.5", "owner promote/demote of folded or suggested items with no LLM call", "build", "P1", "Missing", "AS-PROMOTE"),
    ("AS-QUESTIONS-ROW", "Pack §6.2; §8.7 AC7", "at most 3 questions ranked by structural impact; each with a default; 'Use my defaults'", "build", "P1", "Partial", "AS-QUESTIONS"),
    ("AS-LATENCY-ROW", "Pack §3; §10 X4", "v3 graph: parallel votes + snapshot; streamed read-back <=10 s; no critic/second-look on the blocking path", "build", "P1", "Missing", "AS-LATENCY"),
    ("AS-GOLD-SPANS-ROW", "Pack §9; FIX_PLAN (c)5", "add verbatim spans: to dev and dev2 gold entities and attributes (person-reviewed)", "test", "P1", "Missing", "AS-GOLD-SPANS"),
    ("AS-RECON-BRIEFS", "dev/bakery_ng dev/event_hire dev/clinic_intake gold 'RECONSTRUCTED'", "two headline briefs are reconstructions, not Tope's exact words", "verify", "P1", "Verified", "AS-CH-BRIEF", "DEC-039"),
    ("AS-LIVE-BUDGET", "Pack §10", "live LLM call budget for experiments X0-X4 (~1,000-1,200 calls)", "decision", "P1", "Open", "AS-CONTRACT-EVAL", "DEC-040"),
]
for spec in NEW:
    rid, src, line, typ, pri, st, cards, *dec = spec
    if rid not in by_id:
        r = dict(zip(FIELDS, [rid, src, line, typ, pri, st, cards, dec[0] if dec else ""]))
        rows.append(r)
        by_id[rid] = r

def add_card(rid: str, card: str) -> None:
    cards = [c for c in by_id[rid]["card_ids"].split(";") if c]
    if card not in cards:
        by_id[rid]["card_ids"] = ";".join(cards + [card])

add_card("AS-ANYBRIEF", "AS-TOTAL")
add_card("AS-FAIL-A", "AS-COMPILE")
add_card("AS-FAIL-B", "AS-LEDGER-CALL")
add_card("AS-8.7-AC7", "AS-QUESTIONS")

# Rev 2 (21 Oct, after app-studio/01_REVIEW.md): one v3 orchestrator card, corrected row text, DEC-041.
for rid in ("AS-ANYBRIEF", "AS-LATENCY-ROW", "AS-COMPILE-ROW"):
    add_card(rid, "AS-V3-WIRE")
REV2_TEXT = {
    "AS-RC1": "expanded brief reaches the designer prompt, budget, outline (re-merged), timeout, scope, orphan repair, stock-app suggestions and critic; contract already reads owner words",
    "AS-RC4": "19 env readers choose the App Studio pipeline; one typed profile instead, logged per session and per eval run",
    "AS-LEDGER": "Brief Ledger: clause-cited verbatim quotes (code resolves offsets); entity roles; facts; rules; unsure; validators L1-L8; orphans computed in code",
    "AS-LATENCY-ROW": "v3 graph in one orchestrator (AS-V3-WIRE): parallel votes + contract + snapshot; per-call timeouts; streamed provisional read-back; no critic/second-look on the blocking path",
}
for rid, text in REV2_TEXT.items():
    by_id[rid]["one_line"] = text
if "AS-FIXPLAN-SUPERSEDE" not in by_id:
    r = dict(zip(FIELDS, ["AS-FIXPLAN-SUPERSEDE", "Pack §0; APP_STUDIO_FIX_PLAN (a)(b)",
                          "Pack v3 supersedes FIX_PLAN (a) prompt v2 and (b) stem authorizer under profile v3; fallback stated",
                          "decision", "P1", "Open", "AS-PACK", "DEC-041"]))
    rows.append(r)
    by_id[r["ID"]] = r

# Rev 3 (21 Oct, Tope: senior-Odoo-developer output, no pack crutch; DEC-036..041 resolved).
REV3 = [
    ("AS-CRAFT", "Tope 21 Oct; Pack §6.6; ODOO_CRAFT.md", "craft stage D: every record built with verified senior-Odoo idioms (chatter, sequence, lifecycle, smart buttons, search/report views, security, integrity) per major 17-20", "build", "P1", "Missing", "AS-CRAFT-CATALOG;AS-CRAFT-APPLY;AS-CRAFT-SMART;AS-CRAFT-MODULE"),
    ("AS-CRAFT-LANE", "Pack §6.6 lanes", "which lane gets Python-backed idioms (sequence, counts, totals, constraints, reports): module lane from fixed templates; live lane defers them", "decision", "P1", "Open", "AS-CRAFT-MODULE", "DEC-042"),
    ("AS-CRAFT-EVAL", "Pack §9 craft score", "live craft score per brief and major; release bar >= 95% applicable idioms on the module lane", "test", "P1", "Missing", "AS-CRAFT-SCORE;AS-RELEASE-BARS"),
    ("AS-CRAFT-PLUS", "Tope 21 Oct (beyond smart buttons); ODOO_CRAFT K20-K44", "field behaviour, guided forms/lists/kanban, activities/overdue/email/print, day-one data and upgrade-safe modules", "build", "P1", "Missing", "AS-CRAFT-FIELDS;AS-CRAFT-UX;AS-CRAFT-COMMS;AS-CRAFT-DATA"),
    ("AS-CRAFT-UPGRADES", "ODOO_CRAFT U01-U12", "opt-in senior-developer upgrade chips (portal, payment, invoice, dashboard, approval…); nothing built until clicked", "build", "P2", "Missing", "AS-UPGRADES"),
    ("AS-CRAFT-QUALITY", "ODOO_CRAFT Q1-Q4", "stock-parity score, bounded senior Odoo reviewer (X7), try-it-with-your-data sandbox walkthrough, plain explanation + switch-off per idiom", "build", "P1", "Missing", "AS-CRAFT-PARITY;AS-CRAFT-REVIEW;AS-TRYIT;AS-CRAFT-EXPLAIN"),
    ("AS-NOPACK", "Tope 21 Oct; Pack §0a", "no vertical domain packs on the v3 App Studio path (structure, degraded outline, classification); legacy and Draft Studio unchanged", "build", "P1", "Missing", "AS-NO-PACKS"),
]
for spec in REV3:
    rid, src, line, typ, pri, st, cards, *dec = spec
    if rid not in by_id:
        r = dict(zip(FIELDS, [rid, src, line, typ, pri, st, cards, dec[0] if dec else ""]))
        rows.append(r)
        by_id[rid] = r
add_card("AS-ANYBRIEF", "AS-V3-WIRE")

with LEDGER.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)

pm_path = PLAN / "phase_map.json"
pm = json.loads(pm_path.read_text()) if pm_path.exists() else {}
pm.setdefault("_doc", "card-id prefix -> phase (longest prefix wins). Stage 2 fills the rest.")
pm["AS-"] = 3
pm_path.write_text(json.dumps(pm, indent=2) + "\n")
print(f"rows={len(rows)} as_rows={sum(r['ID'].startswith('AS-') for r in rows)}")

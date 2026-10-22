#!/usr/bin/env python3
"""One-shot scaffold (21 Oct): craft cards beyond smart buttons (ODOO_CRAFT K20-K44, U01-U12, Q1-Q4).

Side effects: writes docs/build-plan/cards/phase-3/<ID>.md for each card below, refusing to overwrite
an existing file. After this run the card files are the source of truth; edit them, not this script.
"""
from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "cards" / "phase-3"
CHARTER = "TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: {b} (caps in budget.json). Stop at 80%."
GATE = ("Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → "
        "Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).")
TAIL = """Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done."""
UI_NOTE = ("The owner-facing screen for this card is built in UI-APPSTUDIO-BUILD to the 07_UI_EXCELLENCE_PROTOCOL bar "
           "(Tope: the absolute best design on every screen); this card ships the API contract and plain copy only.")
ROW_RULE = ("Rows register in the AS-CRAFT-APPLY `ROWS` registry; syntax only from the verified per-version catalog; "
            "every edit carries `craft:Kxx`; never a business record or field (ORACLES K-05).")

CARDS = [
    dict(id="AS-CRAFT-FIELDS", title="Fields that behave like a senior developer set them up (K20-K27)",
         ledger="AS-CRAFT-PLUS", deps="AS-CRAFT-APPLY", b="M", tier="L3", score="6 (C2 U1 F1 K1 V1 I0)",
         ctx=["docs/build-plan/app-studio/ODOO_CRAFT.md rows K20-K27", "docs/build-plan/app-studio/ORACLES.md K-10, K-11"],
         allow=["apps/api/app/ai_conversation/odoo_craft/fields.py (new)", "apps/api/tests/test_odoo_craft_fields.py (new)"],
         goal="Defaults, delete policy, copy flags, indexes, link domains, widgets, owner-worded help and reference search on every owner field.",
         steps=["One row function per K20-K27, registered in `ROWS`", "Help text = the shortest owner quote that created the field (Redactor-restored, escaped)",
                "Live lane: dynamic defaults (today, current user) go to `craft_deferred` unless DEC-042 allows them live"],
         acs=["ORACLES K-10 and K-11 pass unmodified", "No help text contains words outside the cited owner quote (property)"],
         test="tests/test_odoo_craft_fields.py", elite=ROW_RULE),
    dict(id="AS-CRAFT-UX", title="Forms, lists and kanban that guide the user (K28-K35)",
         ledger="AS-CRAFT-PLUS", deps="AS-CRAFT-APPLY, AS-CRAFT-SMART", b="M", tier="L3", score="6 (C2 U1 F1 K1 V1 I0)",
         ctx=["docs/build-plan/app-studio/ODOO_CRAFT.md rows K28-K35", "docs/build-plan/app-studio/ORACLES.md K-12, K-13"],
         allow=["apps/api/app/ai_conversation/odoo_craft/ux.py (new)", "apps/api/tests/test_odoo_craft_ux.py (new)"],
         goal="State-aware forms, ribbons, confirm text, rich kanban cards, empty-state help, default filters, context defaults and inline lines.",
         steps=["One row function per K28-K35, registered in `ROWS`", "State expressions use the 17+ `invisible=`/`readonly=` syntax only; never `attrs`",
                "Empty-state help and confirm text are plain owner language and pass the jargon guard"],
         acs=["ORACLES K-12 and K-13 pass unmodified", "Every emitted view passes the existing per-major view validators",
              "Jargon guard passes on every help and confirm string"],
         test="tests/test_odoo_craft_ux.py", elite=ROW_RULE),
    dict(id="AS-CRAFT-COMMS", title="Work around the record: activities, overdue, email, print (K36-K39)",
         ledger="AS-CRAFT-PLUS", deps="AS-CRAFT-APPLY", b="S", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["docs/build-plan/app-studio/ODOO_CRAFT.md rows K36-K39", "docs/build-plan/app-studio/ORACLES.md K-14"],
         allow=["apps/api/app/ai_conversation/odoo_craft/comms.py (new)", "apps/api/tests/test_odoo_craft_comms.py (new)"],
         goal="Activity types from the owner's reminder rules, overdue filters and decorations, and email/print only when the owner asked.",
         steps=["K36/K37 rows from rules and date + lifecycle facts", "K38 only when a cited owner quote says send/email/share; K39 extends K16",
                "No outbound email is ever sent by App Studio itself (INV-18): templates and buttons only"],
         acs=["ORACLES K-14 passes unmodified", "No K38 element without a cited owner quote (property)"],
         test="tests/test_odoo_craft_comms.py", elite=ROW_RULE),
    dict(id="AS-CRAFT-DATA", title="Ready on day one: ordered selections, lookup data, import templates, upgrade-safe data (K40-K44)",
         ledger="AS-CRAFT-PLUS", deps="AS-CRAFT-APPLY, AS-CRAFT-MODULE", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["docs/build-plan/app-studio/ODOO_CRAFT.md rows K40-K44", "docs/build-plan/app-studio/ORACLES.md K-15"],
         allow=["apps/api/app/ai_conversation/odoo_craft/data.py (new)", "apps/api/app/ai_conversation/odoo_craft/module_templates/ (data + import template files only)",
                "apps/api/tests/test_odoo_craft_data.py (new)"],
         goal="Owner-listed values and lookup records exist as data, each record has an import template, and module data survives upgrades.",
         steps=["K40/K41 from verbatim listed values only", "K42 import template columns in form order",
                "K43/K44 checks run inside the existing structural zip gate"],
         acs=["ORACLES K-15 passes unmodified", "Reinstalling the module over owner-edited data keeps the edits (sandbox test, GATE-A)"],
         test="tests/test_odoo_craft_data.py", elite=ROW_RULE),
    dict(id="AS-UPGRADES", title="Suggested upgrades a senior developer would offer (U01-U12), opt-in only",
         ledger="AS-CRAFT-UPGRADES", deps="AS-CRAFT-APPLY, AS-PROMOTE", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["docs/build-plan/app-studio/ODOO_CRAFT.md 'Suggested upgrades'", "docs/build-plan/app-studio/00_PACK.md §6.5", "docs/build-plan/app-studio/ORACLES.md K-16"],
         allow=["apps/api/app/ai_conversation/odoo_craft/upgrades.py (new)", "apps/api/tests/test_odoo_craft_upgrades.py (new)"],
         goal="At most 3 upgrade chips per screen, each with one plain sentence; nothing is built until the owner clicks, then Promote applies it with no LLM call.",
         steps=["Offer rules exactly as the U table, from ledger shape + snapshot (installed / installable apps)",
                "Never offer an upgrade the owner excluded (left_out not_wanted) or a module the hosting lane cannot install",
                "Click → `owner_override` → re-run C, D, A (same path as Promote)", UI_NOTE],
         acs=["ORACLES K-16 passes unmodified", "An offered upgrade adds 0 elements until clicked (property)", "Never more than 3 chips (property)"],
         test="tests/test_odoo_craft_upgrades.py", elite="Upgrades are suggestions, not craft: they never count as invented because nothing exists until the owner asks."),
    dict(id="AS-CRAFT-PARITY", title="Stock-parity score: does it sit next to stock Odoo apps without looking amateur? (Q1)",
         ledger="AS-CRAFT-QUALITY", deps="AS-CRAFT-CATALOG, AS-CRAFT-SCORE", b="M", tier="L2", score="5 (C1 U1 F1 K1 V1 I0)",
         ctx=["docs/build-plan/app-studio/ODOO_CRAFT.md 'Quality systems' Q1", "AS-CRAFT-CATALOG probe output (stock exemplar views per major)"],
         allow=["apps/api/evals/v2/craft_parity.py (new)", "apps/api/evals/v2/tests/test_craft_parity.py (new)"],
         goal="For each generated view, list the features its stock exemplar of the same shape has (header, button box, chatter, filters, group-bys, sums, kanban card parts) and report every gap.",
         steps=["Exemplar per shape: document with lines → sale.order; pipeline → crm.lead; task-like → project.task; contact-like → res.partner",
                "Feature extraction is the same parser for both sides", "Report gaps per brief, per major"],
         acs=["Synthetic pair (exemplar vs a view missing chatter and filters) reports exactly those 2 gaps",
              "Release bar in AS-RELEASE-BARS: 0 gaps that the exemplar of the same shape has, on the module lane"],
         test="evals/v2/tests/test_craft_parity.py", elite="Stock views are the reference for 'world-class'. Read them over RPC; never copy Enterprise or Studio code (INV-12)."),
    dict(id="AS-CRAFT-REVIEW", title="Senior Odoo reviewer: one bounded LLM pass that may only propose catalog rows (Q2, experiment X7)",
         ledger="AS-CRAFT-QUALITY", deps="AS-CRAFT-APPLY, AS-UPGRADES, AS-CRAFT-SCORE", b="M", tier="L3", score="7 (C2 U2 F1 K1 V1 I0)",
         ctx=["docs/build-plan/app-studio/ODOO_CRAFT.md Q2", "docs/build-plan/app-studio/00_PACK.md §3 (call count), §7 (deadlines)"],
         allow=["apps/api/app/ai_conversation/odoo_craft/review.py (new)", "apps/api/tests/test_odoo_craft_review.py (new)",
                "apps/api/evals/v2/experiments/x7_craft_review.md (new; results only)"],
         goal="An optional call reads the built design (no owner free text beyond the fenced brief) and returns `[{row_id, target, reason}]`; code applies only K rows whose trigger holds and turns U ids into chips; everything else is dropped and logged.",
         steps=["Schema-constrained output (AS-DECODE); row ids must exist in the catalog", "Runs only when time remains before the soft deadline; counts toward Pack §3's call budget",
                "X7: paired run with and without the reviewer on dev + dev2; keep it only if Tope's rating rises with craft score and invention unchanged"],
         acs=["A reviewer output naming a new model or an unknown row is fully dropped (unit test)",
              "X7 result written with paired CIs; profile default stays off until X7 passes"],
         test="tests/test_odoo_craft_review.py", elite="AI proposes, code authorises (INV-13): the reviewer can never add structure, only point at catalog rows."),
    dict(id="AS-TRYIT", title="Try it with your data: sandbox walkthrough before install (Q3)",
         ledger="AS-CRAFT-QUALITY", deps="AS-CRAFT-MODULE, AS-CRAFT-DATA", b="L", tier="L3", score="7 (C2 U1 F1 K1 V2 I0)",
         ctx=["docs/build-plan/app-studio/ODOO_CRAFT.md Q3", "INV-03 (disposable ingenium_* DBs), INV-15 (honest data)"],
         allow=["apps/api/app/ai_conversation/try_it.py (new)", "apps/api/app/routers/ai_studio.py (new route `POST /{id}/try`)", "apps/api/tests/test_try_it.py (new)"],
         goal="After a sandbox install, load 5-20 rows from the owner's own spreadsheet (via the K42 import template and Universal Ingest) or clearly labelled Example rows, and run a scripted walkthrough: create, move state, open a smart button, print.",
         steps=["Sandbox only: a disposable `ingenium_try_<session>` DB, dropped after 24 h or on install", "Owner rows never leave the sandbox; Example rows are labelled 'Example' everywhere (INV-15)",
                "Walkthrough steps and their results return as plain events", UI_NOTE],
         acs=["Walkthrough on bakery_ng with Example rows passes every step on a disposable v19 sandbox (GATE-A)",
              "The DB is dropped by the cleanup job (test lists DBs before/after)", "No owner row appears in any log (scrub test, INV-17)"],
         test="tests/test_try_it.py", elite="This touches customer data in a sandbox: disposable DB only, never a client DB, never logged."),
    dict(id="AS-CRAFT-EXPLAIN", title="Explain every idiom in one plain sentence, and let the owner switch it off (Q4)",
         ledger="AS-CRAFT-QUALITY", deps="AS-CRAFT-APPLY", b="S", tier="L2", score="4 (C1 U1 F1 K1 V0 I0)",
         ctx=["docs/build-plan/app-studio/ODOO_CRAFT.md Q4", "handover Appendix C (glossary)"],
         allow=["apps/api/app/ai_conversation/odoo_craft/explain.py (new)", "apps/api/tests/test_odoo_craft_explain.py (new)"],
         goal="Each K row has one owner sentence ('Added a reference number so you can find orders by number'); each craft edit can be switched off through `owner_override`.",
         steps=["One sentence per K row, filled with the record's owner label", "Switch-off re-runs D and A with that row excluded for that record", UI_NOTE],
         acs=["Every registered K row has a sentence (test fails on a missing one)", "Jargon guard passes on all sentences", "Switch-off survives regenerate"],
         test="tests/test_odoo_craft_explain.py", elite="Plain language is an invariant (INV-04): no 'mixin', 'compute', 'xpath' or 'IR' in owner copy."),
]


def render(c: dict) -> str:
    lines = [f"# {c['id']}: {c['title']}", "", f"ID: {c['id']}", f"Title: {c['title']}", "Status: todo", "Phase: 3",
             "Priority: P1", "Type: build", CHARTER.format(b=c["b"]), f"Ledger IDs: {c['ledger']}", f"Depends on: {c['deps']}",
             f"Routing: Worker: {c['tier']} (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: {c['tier']} separate session · Score: {c['score']}",
             "Context pack:"] + [f"- {x}" for x in c["ctx"]] + ["File allow-list:"] + [f"- {x}" for x in c["allow"]]
    lines += [f"Goal: {c['goal']}", "Steps:"] + [f"{i}. {s}" for i, s in enumerate(c["steps"], 1)]
    lines += ["Acceptance criteria:"] + [f"- AC{i}: {a}" for i, a in enumerate(c["acs"], 1)]
    lines += ["Test plan:", f"- `cd apps/api && uv run pytest -q {c['test']}`", f"Elite design notes: {c['elite']}",
              "Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.", GATE, TAIL, ""]
    return "\n".join(lines)


def main() -> int:
    for c in CARDS:
        path = OUT / f"{c['id']}.md"
        if path.exists():
            print(f"skip {path.name} (exists)")
            continue
        path.write_text(render(c))
        print(f"wrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

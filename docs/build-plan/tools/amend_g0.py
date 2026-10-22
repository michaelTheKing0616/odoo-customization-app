#!/usr/bin/env python3
"""G0 amendments (21 Oct): apply Tope's answers to ledger.csv. Idempotent.

Side effects: rewrites docs/build-plan/ledger.csv in place. Reads docs/specs/* and
docs/plans/next-phase/14_WORK_CARDS.md. Prints a one-line summary.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "docs/build-plan/ledger.csv"
OLD_INDEX = ROOT / "docs/plans/next-phase/14_WORK_CARDS.md"

rows = list(csv.DictReader(LEDGER.open()))
FIELDS = list(rows[0].keys())
by_id = {r["ID"]: r for r in rows}


def upd(rid: str, **kw: str) -> None:
    by_id[rid].update(kw)


def add(rid, src, line, typ, pri, status, cards, dec=""):
    if rid in by_id:
        return
    r = dict(zip(FIELDS, [rid, src, line, typ, pri, status, cards, dec]))
    rows.append(r)
    by_id[rid] = r


# --- Resolved decisions -------------------------------------------------------
upd("AS-FAIL-C", source_section="APP_STUDIO_HANDOFF §4C; FIX_PLAN D/C",
    one_line="failure C: need coverage 0.53 (renamed main entity; stock route not matched by stems)",
    type="build", status_label_today="Open", card_ids="AS-PACK;AS-COVERAGE", tope_decision="")
upd("AS-REPORTED-FIVE", status_label_today="Reported-by-Tope", tope_decision="",
    one_line="five headline briefs named 21 Oct: Customer Health (no file) + rental_casual rental_structured bakery_ng event_hire (dev)")
upd("AS-REPORTED-CH", status_label_today="Reported-by-Tope", tope_decision="")
add("AS-CH-BRIEF", "Tope 21 Oct", "copy tests/fixtures/customer_health_brief.md to evals/v2/dev/customer_health.md + person-reviewed gold",
    "test", "P1", "Missing", "AS-CH-BRIEF", "DEC-037")
upd("H-3.9-DEADLETTER", status_label_today="Resolved",
    one_line="dead letter = MAX_ATTEMPTS 6 (first try + 5 retries; delivery.py L30); §7.8 wording corrected", tope_decision="")
add("REL-BR-RETRYWINDOW", "delivery.py L30-56 (read 21 Oct)",
    "retry window is ~62 s (2+4+8+16+32 s); 900 s cap never reached; a 2-minute partner outage dead-letters every event",
    "build", "P1", "Verified", "BR-RETRY-WINDOW", "DEC-036")
for r in rows:
    dec = r["tope_decision"]
    if dec == "DEC-020":
        r["status_label_today"] = "Resolved"
        r["one_line"] = "self-approval: any requester may self-approve (audited; §2.4 wins; §6.5 corrected)"
    if dec == "DEC-022":
        r["status_label_today"] = "Resolved"
        r["card_ids"] = r["card_ids"] or "NP-MERGE"
    if dec in ("DEC-020", "DEC-021", "DEC-022", "DEC-035", "DEC-030", "DEC-001"):
        r["tope_decision"] = ""
        r["card_ids"] = r["card_ids"] or "DOC-HANDOVER-ERRATA"
upd("SEC-6.5-AC2", status_label_today="Resolved",
    one_line="INVERTED by Tope 21 Oct: self-approval allowed for any requester; test asserts it is audited (who/when/plan hash) and still passes money guard + dry-run receipt")

# --- Spec intake (DEC-002) ----------------------------------------------------
for rid in ("DOC-SPEC-SPEC", "DOC-SPEC-CSS", "DOC-SPEC-BRS", "DOC-SPEC-AS"):
    upd(rid, status_label_today="Done", tope_decision="")
upd("DOC-SPEC-GAP", status_label_today="Partial", tope_decision="DEC-038",
    one_line="GAP_AUDIT copied 21 Oct; builders PROGRESS.md + stage3/contrast.md still box-only")
upd("DOC-SPEC-BRAND", status_label_today="Partial", tope_decision="DEC-038",
    one_line="brand SVGs present (docs/brand, public/brand); BRAND_GUIDE.md + brand tokens.css + DESIGN_SYSTEM_PLAYBOOK.md still box-only")
upd("DT-BOXMATCH", status_label_today="Verified 21 Oct", tope_decision="",
    one_line="docs/specs copies of DESIGN_TOUCHES + FEATURE_AUDIT are byte-identical to docs/ (cmp 21 Oct)")
for rid in ("H-3.5-SPECROLL", "SUITE-COMMON"):
    upd(rid, tope_decision="")
for rid, fam in (("VD-SPEC-ROLLUP", "VD-G-*"), ("SUITE-SPEC-ROLLUP", "SUITE-TOOL-*;BULK-*"),
                 ("BRIDGE-SPEC-ROLLUP", "BR-ITEM-*"), ("CR-SPEC-ROLLUP", "CR-ITEM-*")):
    upd(rid, status_label_today="Itemised", tope_decision="", card_ids=by_id[rid]["card_ids"])

# --- BRIDGE_RUNNER_SPEC items (status: GAP_AUDIT §3 + G5/G9 updates) -----------
brs = (ROOT / "docs/specs/BRIDGE_RUNNER_SPEC.md").read_text()


def items(section: str) -> list[tuple[int, str]]:
    """Split a one-line numbered list ('1 Foo. 2 Bar.') by expecting 1..N in order."""
    count = int(re.search(r"\((\d+)\)", section).group(1))
    body = brs.split(section, 1)[1].strip().split("\n", 1)[0]
    starts, pos = [], 0
    for k in range(1, count + 1):
        m = re.compile(rf"(?:^|(?<=\. )){k} (?=[A-Z])").search(body, pos)
        if not m:
            raise SystemExit(f"{section}: item {k} not found")
        starts.append(m.start())
        pos = m.end()
    starts.append(len(body))
    return [(k + 1, body[starts[k]:starts[k + 1]].split(" ", 1)[1].strip().rstrip(".")[:110]) for k in range(count)]


cr_partial = {1: "V-CR-SPLIT", 18: "V-CR-PROFILE", 24: "CR-COEDIT"}
for n, text in items("## Code runner (29)"):
    st = "Partial" if n in cr_partial else "Done-code"
    add(f"CR-ITEM-{n:02d}", f"BRIDGE_RUNNER_SPEC CR {n}; GAP §3", text.replace(",", ";"), "regression" if st != "Partial" else "build",
        "P2", st, cr_partial.get(n, "REG-CR-LIVE;CR-CLICK"))
br_partial = {2: "BR-AISPEC-DRAFT;BR-AISPEC-VALIDATE;BR-AISPEC-EVAL", 3: "BR-OAUTH", 5: "BR-CANVAS-CORE;BR-CANVAS-LIVE;BR-CANVAS-PERF;BR-CANVAS-VERSION",
              10: "L2-PROVE-DELIVERY", 11: "L2-PROVE-DELIVERY;BR-RETRY-WINDOW", 14: "BR-DRIFT", 19: "BR-MONITOR", 23: "BR-MONITOR",
              24: "V-BR-DOCKERFILE", 31: "REG-BR-PII"}
for n, text in items("## Bridge (32)"):
    st = "Partial" if n in br_partial else "Done-code"
    add(f"BR-ITEM-{n:02d}", f"BRIDGE_RUNNER_SPEC Bridge {n}; GAP §3", text.replace(",", ";"),
        "build" if st == "Partial" else "regression", "P1" if n in (5, 11) else "P2", st, br_partial.get(n, "REG-BR-LIVE"))
cache = {"a": ("shared AI client for every call site", "Done-code", "REG-AI-GUARDS"),
         "b": ("exact-response cache keyed model+prompt+inputs+snapshot hash; TTL; invalidation", "Done-code", "REG-AI-GUARDS;B0-AICACHE-ISO"),
         "c": ("provider prompt/context caching for stable prefixes", "Done-code", "REG-AI-GUARDS"),
         "d": ("semantic cache for near-duplicates with confidence floor", "Missing", "CACHE-SEM"),
         "e": ("cache deterministic sub-results per database", "Done-code", "REG-AI-GUARDS"),
         "f": ("batch calls", "Partial", "CACHE-BATCH"),
         "g": ("cost dashboard: hit rate and money saved", "Done-code", "REG-AI-GUARDS"),
         "h": ("never cache secrets/PII; fresh-answer bypass", "Done-code", "SEC-CACHE-SECRETS")}
for k, (t, st, c) in cache.items():
    add(f"CACHE-{k.upper()}", f"BRIDGE_RUNNER_SPEC LLM caching ({k}); GAP §3", t, "build" if st != "Done-code" else "regression", "P1", st, c)
guards = {1: ("injection classifier on all untrusted text; fenced as data", "Partial", "V-AI-INJECT-ALL"),
          2: ("PII/secret redaction before any cloud call; restored after", "Done-code", "REG-AI-GUARDS"),
          3: ("output checker: no secrets/other-client data/prompt leaks; honesty labels; DB claims verified", "Done-code", "REG-AI-GUARDS"),
          4: ("topic guard for client-facing chat", "Done-code", "REG-AI-GUARDS"),
          5: ("every flag logged to History; red-team pack before each release", "Done-code", "SEC-REDTEAM-EXT;GATE-R")}
for n, (t, st, c) in guards.items():
    add(f"GUARD-{n}", f"BRIDGE_RUNNER_SPEC AI guards {n}; GAP §3 + update #3", t, "security", "P1", st, c)

# --- SPEC.md items not already carded (GAP §1) --------------------------------
vd = [("VD-G-ENGINE", "§2 engine load/normalize/compile/publish/revert", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-STAGE12", "§11 stage 1-2 logic (conditions role preview history comments cmd bar proof loop)", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-STAGE34", "§11 stage 3-4 contrast keyboard INP (G9 live)", "Done-live", "REG-VD-STAGE34"),
      ("VD-G-STITCH", "§14 Stitch adopts (chip bar drop label pinned comments hint strip tab badges publish count)", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-WHOSEE", "§15 who-can-see editable; impact words; why hidden", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-TIDY", "§16 tidy up + screen health score", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-HISTORY", "§16 history scrubber", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-REUSE", "§16 reusable sections + move layout between DBs", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-PRESENCE", "§16 presence / co-edit", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-REPORTS", "§16 reports: blocks anywhere conditional QR/barcode watermark email previews", "Done-code", "REG-RD-EMAIL"),
      ("VD-G-HEATMAP", "§18 heatmap; pivot/graph designer; a11y simulator", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-2D", "§19 2d ideas 2 3 4 5 13 16 17 18 19 20", "Partial", "VD-APPROVERS;V-VD-SCHED"),
      ("VD-G-AIEDIT", "§20.1 Edit with AI (views reports emails)", "Done-code", "REG-VD-STAGE34"),
      ("VD-G-AVATARS", "§20.2 Expert + bot avatars", "Done-code", "REG-VD-STAGE34")]
for rid, t, st, c in vd:
    add(rid, f"SPEC {t.split()[0]}; GAP §1", t, "regression" if st.startswith("Done") else "build", "P2", st, c)

# --- CONFIG_SUITE_SPEC: 15 tools + Bulk Setup sections --------------------------
css = (ROOT / "docs/specs/CONFIG_SUITE_SPEC.md").read_text().splitlines()
for i, line in enumerate(css, 1):
    m = re.match(r"### 6\.(\d+b?) (.+)", line)
    if m:
        add(f"SUITE-TOOL-{m.group(1).upper()}", f"CONFIG_SUITE_SPEC §6.{m.group(1)} L{i}", m.group(2).replace(",", ";")[:110],
            "regression", "P2", "Done-live", "REG-SUITE-LIVE;UI-SUITE-BUILD")
    m = re.match(r"### 20\.(\d+) (.+)", line)
    if m and m.group(1) not in ("2", "14"):
        add(f"BULK-20-{m.group(1)}", f"CONFIG_SUITE_SPEC §20.{m.group(1)} L{i}", m.group(2).replace(",", ";")[:110],
            "regression", "P2", "Done-live" if m.group(1) in ("12",) else "Done-code", "REG-SUITE-LIVE;UI-SUITE-BUILD")
    m = re.match(r"### 7\.(\d) (.+)", line)
    if m:
        add(f"SUITE-SAFE-7-{m.group(1)}", f"CONFIG_SUITE_SPEC §7.{m.group(1)} L{i}", m.group(2).replace(",", ";")[:110],
            "invariant", "P1", "Done-code", "REG-SUITE-LIVE;UI-SAFETY-BUILD")

# --- APP_STUDIO_FIX_PLAN steps (GAP §5) ---------------------------------------
fix = [("AS-FIX-1", "metric fixes + record/replay + re-baseline", "Done-code", "REG-AS-REPLAY"),
       ("AS-FIX-2", "model_authorizer offline (pure; idempotent; never adds; bias to fold; spans verified)", "Done-code", "AS-AUTHZ"),
       ("AS-FIX-3", "schema+prompt change + 3 discriminating experiments (brief-contract fix paused)", "Partial", "AS-PACK;AS-PROMPT-CONTRACT"),
       ("AS-FIX-4", "python gate + orphan repair", "Done-code", "REG-AS-ORPHAN"),
       ("AS-FIX-5", "shadow mode ~1 week on real sessions", "Missing", "AS-SHADOW"),
       ("AS-FIX-6", "fresh holdout before claiming", "Partial", "AS-HOLDOUT-RUN"),
       ("AS-FIX-CONSERVE", "D/C shared cause: conservation law (every brief clause lands in exactly one bucket)", "Missing", "AS-PACK;AS-CONSERVE"),
       ("AS-FIX-EVAL", "eval changes (c): repeats; seeds; entity matching beyond stems; CI; suggested vs built", "Partial", "AS-PACK;AS-EVAL-FAIR")]
for rid, t, st, c in fix:
    add(rid, "APP_STUDIO_FIX_PLAN; GAP §5", t, "build" if not st.startswith("Done") else "regression", "P1", st, c)
add("AS-ANYBRIEF", "Tope 21 Oct", "App Studio never errors on any brief (unstructured; non-technical; code-switched; huge; empty; hostile): every brief ends valid design | <=3 questions | named left-out | honest decline",
    "build", "P0", "Missing", "AS-PACK;AS-ROBUST-FUZZ")

# --- UI reference map (Tope 21 Oct) -------------------------------------------
ui = [("01", "Shell; lists; History", "Linear; Stripe Dashboard", "UI-SHELL-SPEC;UI-SHELL-BUILD;UI-HISTORY-SPEC;UI-HISTORY-BUILD"),
      ("02", "Cmd-K", "Raycast", "F1-CMDK"),
      ("03", "Sidebar and database switcher", "Arc; Vercel; Apple Wallet", "F1-NAV;F1-SWITCHER;F1-SWITCHER-UX"),
      ("04", "Home and agency view", "Stripe; Vercel", "UI-HOME-SPEC;UI-HOME-BUILD"),
      ("05", "Approvals", "Superhuman; Linear Inbox", "UI-APPROVALS-SPEC;UI-APPROVALS-BUILD"),
      ("06", "Connect and onboarding", "Stripe; Vercel", "UI-CONNECT-SPEC;UI-CONNECT-BUILD;UI-ONBOARD-SPEC;UI-ONBOARD-BUILD"),
      ("07", "App Studio", "Claude app; Cursor; v0", "UI-APPSTUDIO-SPEC;UI-APPSTUDIO-BUILD"),
      ("08", "View and Report Designer canvas", "Figma; Framer; Webflow", "UI-VD-SPEC;UI-VD-BUILD;UI-RD-SPEC;UI-RD-BUILD"),
      ("09", "Records tables", "Attio; Notion; Airtable", "UI-RECORDS-SPEC;UI-RECORDS-BUILD"),
      ("10", "Bridge flow canvas", "n8n; Make", "BR-CANVAS-CORE;BR-CANVAS-LIVE"),
      ("11", "Code Runner", "Zed; Cursor; Warp", "UI-CR-SPEC;UI-CR-BUILD"),
      ("12", "Bots", "Claude app; Cursor agent; Grok app", "UI-BOTS-SPEC;UI-BOTS-BUILD"),
      ("13", "Live Demo Co-Pilot panel", "Granola; Fathom", "UI-COPILOT-SPEC;UI-COPILOT-BUILD"),
      ("14", "Money guard and safety", "Stripe; Mercury", "UI-SAFETY-SPEC;UI-SAFETY-BUILD"),
      ("15", "Settings and billing", "Linear; Stripe", "UI-SETTINGS-SPEC;UI-SETTINGS-BUILD;UI-BILLING-SPEC;UI-BILLING-BUILD"),
      ("16", "Charts", "Stripe; Vercel; Linear Insights", "UI-CHARTS-SPEC;UI-CHARTS-BUILD"),
      ("17", "Empty states", "Things 3; Arc", "F1-STATES;UI-EMPTY-SPEC"),
      ("18", "Mobile", "Linear; Superhuman; Things", "F1-RESPONSIVE;UI-MOBILE-SPEC;UI-MOBILE-BUILD"),
      ("19", "Docs", "Stripe docs; Linear docs", "UI-DOCS-SPEC;UI-DOCS-BUILD")]
for n, area, refs, cards in ui:
    add(f"UIX-{n}", f"Tope 21 Oct map; pack {n}", f"rebuild {area} to the bar of {refs} (3-5 adopted patterns; side-by-side before done)",
        "ui-build", "P1", "Poor (Tope 21 Oct)", cards)
add("UIX-00", "Tope 21 Oct", "whole-app UI is 'really really poor': score every route against its pack area; baseline contact sheets; no screen ships below bar",
    "ui-build", "P0", "Poor (Tope 21 Oct)", "UI-AUDIT-ALL;UI-REF-STUDY")
add("UIX-TOUCHES", "Tope 21 Oct; DESIGN_TOUCHES", "all 162 design touches implemented in full; built ones re-checked inside their area rebuild",
    "ui-build", "P1", "Partial", "UI-AUDIT-ALL;REG-TOUCH-01;REG-TOUCH-02;REG-TOUCH-03;REG-TOUCH-04;REG-TOUCH-05;REG-TOUCH-06")
for r in rows:
    if r["ID"].startswith("TOUCH-") and r["status_label_today"] == "Built-partial":
        r["type"] = "ui-build"
        r["card_ids"] = r["card_ids"] + ";TOUCH-COMPLETE"

# --- Old pack docs/plans/next-phase (DEC-022: merged; IDs reused verbatim) -------
STATUS = {"DONE": "Done-code", "SEEDED": "Partial", "PARTIAL": "Partial", "OPEN": "Missing",
          "OPERATOR": "Operator", "BLOCKED": "Blocked"}
own_cards = {c for r in rows for c in r["card_ids"].split(";")}
for line in OLD_INDEX.read_text().splitlines():
    m = re.match(r"^\|\s*([A-Z0-9][A-Z0-9]*-[A-Z0-9-]+)\s*\|\s*([^|]+?)\s*\|\s*([A-Z]+)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*`?([^|`]*)`?", line)
    if not m:
        continue
    oid, title, st, pressure, band, f = m.groups()
    track = oid.split("-")[0]
    card = f"REG-NP-{track}" if st == "DONE" else (oid if oid not in own_cards else f"NP.{oid}")
    add(f"NP-{oid}", f"next-phase {f.strip() or '14_WORK_CARDS'}", f"{title.replace(',', ';')[:100]} (pressure {pressure})",
        "regression" if st == "DONE" else "build", "P1" if st in ("SEEDED", "PARTIAL") else "P2", STATUS.get(st, st), card,
        "DEC-013" if st == "OPERATOR" and "letter" in title.lower() else "")

with LEDGER.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
print(f"rows={len(rows)} np={sum(r['ID'].startswith('NP-') for r in rows)} "
      f"br={sum(r['ID'].startswith('BR-ITEM') for r in rows)} cr={sum(r['ID'].startswith('CR-ITEM') for r in rows)} "
      f"uix={sum(r['ID'].startswith('UIX') for r in rows)}")

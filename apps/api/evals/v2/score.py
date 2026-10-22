"""Eval v2 scorer. Calls the SAME entrypoint as the App Studio button: POST /api/ai/sessions (diagnosis,
which builds the app design) then POST /api/ai/sessions/{id}/generate (draft). Never installs anything.

usage: uv run python evals/v2/score.py --split dev --repeats 3 --out /tmp/evals_v2_baseline.json [--metamorphic]
"""
import argparse, concurrent.futures as cf, hashlib, json, os, pathlib, re, statistics, sys, time, urllib.request as u

import yaml

ROOT = pathlib.Path(__file__).parent
API = os.environ.get("EVAL_API", "http://127.0.0.1:8001")
CONN = os.environ.get("EVAL_CONNECTION", "")
FORBIDDEN_CONNECTIONS = {"bf32709f-a2e5-49ba-b2e7-146321fddb02"}  # aonb: never an eval target
FRESH = os.environ.get("EVAL_FRESH") == "1"
SEVERITY = {"model": 3.0, "automation": 2.0, "exclusion_violated": 5.0, "field": 0.2}
sys.path.insert(0, str(ROOT.parent.parent))


def post(path, body, timeout=900):
    headers = {"Content-Type": "application/json"}
    if FRESH:
        headers["x-ingenium-fresh"] = "1"  # fresh session: no cached AI answers from earlier runs
    r = u.Request(API + path, data=json.dumps(body).encode(), headers=headers, method="POST")
    with u.urlopen(r, timeout=timeout) as x:
        return json.loads(x.read())


def _designs(o):
    if isinstance(o, dict):
        if isinstance(o.get("new_models"), list) and "app_name" in o:
            yield o
        for v in o.values():
            yield from _designs(v)
    elif isinstance(o, list):
        for v in o:
            yield from _designs(v)


def find_design(o):
    """The richest app design in the session (the diagnosis copy, not an empty top-level stub)."""
    found = list(_designs(o))
    return max(found, key=lambda d: (len(d.get("new_models") or []), len(d.get("stock_extensions") or [])), default=None)


def stems(t):
    out = set()
    for w in re.findall(r"[a-z]{3,}", (t or "").lower()):
        for suf in ("ing", "ies", "es", "s", "ed"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)]
                break
        out.add(w[:6])
    return out - {"the", "and", "for", "record", "log", "line", "x_"}


def match(a, b):
    sa, sb = stems(a), stems(b)
    return any(x == y or (min(len(x), len(y)) >= 4 and (x.startswith(y) or y.startswith(x))) for x in sa for y in sb)


def run_case(cid, brief):
    t = time.time()
    s = post("/api/ai/sessions", {"connection_id": CONN, "prompt": brief})
    sid = s.get("id") or s.get("session_id")
    conv = s.get("conversation") or []
    last = conv[-1] if conv else {}
    md = (last.get("metadata") or {}) if isinstance(last, dict) else {}
    kind = ((md.get("clarification") or {}).get("kind")) or md.get("kind") or ""
    q = (md.get("clarification") or {}).get("question") or ""
    design = find_design(s)
    clar = (md.get("clarification") or {}) if isinstance(md, dict) else {}
    routes_nd = clar.get("integration_routes") or []
    decision = clar.get("diagnosis_decision")
    t_diag = time.time() - t
    draft = None
    if design and kind == "diagnosis" and sid and os.environ.get("EVAL_GENERATE", "1") == "1":
        try:
            draft = post(f"/api/ai/sessions/{sid}/generate", {})
        except Exception as exc:  # noqa: BLE001
            draft = {"error": str(exc)[:200]}
    return {"id": cid, "kind": kind, "question": q, "design": design, "routes_nodesign": routes_nd,
            "diagnosis_decision": decision, "latency_s": round(time.time() - t, 1),
            "latency_diag_s": round(t_diag, 1), "draft_status": (draft or {}).get("status") if isinstance(draft, dict) else None,
            "chars": len(brief) + len(json.dumps(design or {})),
            "llm_calls": llm_calls(((s.get("understanding") or {}).get("llm_outcome")) or (design or {}).get("llm_outcome") or {}),
            "signature": signature(design or {}),
            "agent": {k: ((design or {}).get("llm_outcome") or {}).get(k) for k in
                      ("mode", "model", "tool_calls", "llm_calls", "in_tok", "out_tok", "think_tok", "usd_est",
                       "remaining_issues", "fix_round")} if ((design or {}).get("llm_outcome") or {}).get("mode") == "agent" else None}


_STOCK_HINT = re.compile(r"(?i)\b(sale_renting|rental|maintenance|helpdesk|employees|hr|invoicing|account|sales|sale\.order|"
                         r"inventory|stock|events?|field service|planning|crm|project)\b")


def signature(d):
    """Canonical design signature: multiset of host model|NEW, field type, relation target class,
    automation shape and access rule; names normalized away (metamorphic equivalence)."""
    new = {m.get("name") for m in d.get("new_models") or []}
    out = []
    for m in d.get("new_models") or []:
        for f in m.get("fields") or []:
            rel = f.get("relation") or ""
            out.append(("NEW", f.get("ttype"), "new" if rel in new else ("stock" if rel else "-")))
    for e in d.get("stock_extensions") or []:
        for f in e.get("fields") or []:
            out.append((e.get("model"), f.get("ttype"), "stock" if f.get("relation") else "-"))
    for a in d.get("automations") or []:
        sp = a.get("automation") or {}
        out.append(("AUTO", sp.get("when"), sp.get("action")))
    for r in d.get("record_rules") or []:
        out.append(("ACCESS", r.get("scope"), "-"))
    return sorted(map(str, out))


def sig_similarity(a, b):
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    inter, union = sum((ca & cb).values()), sum((ca | cb).values())
    return round(inter / union, 3) if union else 1.0


def llm_calls(o):
    n = 0
    if isinstance(o, dict):
        n += 1 if o.get("status") == "called" else 0
        if o.get("mode") == "agent":  # agent mode: every round trip of its tool loop is a call
            n += max(0, int(o.get("llm_calls") or 0) - 1)
        n += 1 if o.get("batched_with_verifier") else 0  # verifier ran alongside the design call
        n += 1 if isinstance(o.get("grounding"), dict) else 0  # clause-mode classify call (parallel)
        n += sum(llm_calls(v) for v in o.values() if isinstance(v, (dict, list)))
    elif isinstance(o, list):
        n += sum(llm_calls(v) for v in o)
    return n


def score(gold, r):
    """Need-level scoring: entities/automations/access are needs with acceptable realizations
    (custom or a stock alternative). Field names are never scored."""
    d = r["design"] or {}
    models = [m.get("label") or m.get("name") for m in d.get("new_models") or []]
    exts = [e.get("model") for e in d.get("stock_extensions") or []]
    apps = [i.get("module") or i.get("app") for i in d.get("integrations") or []] + \
           [s_.get("module") for s_ in d.get("stock_suggestions") or []]
    stock_blob = " ".join(map(str, exts + apps))
    autos = [a.get("label", "") for a in d.get("automations") or []] + [p.get("label", "") for p in d.get("python_needed") or []]
    rules = [x.get("label", "") for x in d.get("record_rules") or []]
    needs = gold.get("needs") or []
    # records moved onto a stock host by stock-first (host extended with fields): the need is held there
    ext_hosts = {e.get("model") for e in d.get("stock_extensions") or [] if e.get("fields")}
    moved = [str(c.get("converted")) for c in d.get("stock_checks") or []
             if c.get("converted") and (c.get("use") or {}).get("model") in ext_hosts]
    met, reinvented = 0, 0
    for nd in needs:
        name = nd["need"].split("(")[0].replace("keep", "").replace("records", "")
        if nd["kind"] == "records":
            custom = any(match(name, m) for m in models)
            on_host = any(match(name, m) for m in moved)
            stock_alt = [x for x in nd["realizations"][1:] if _STOCK_HINT.search(x)]
            # any stock app named in the realization (not just the first hint word, e.g. "use stock Sales (sale.order)")
            stock_used = any(m.group(0).lower() in stock_blob.lower() for x in stock_alt for m in _STOCK_HINT.finditer(x))
            met += 1 if (custom or stock_used or on_host) else 0
            reinvented += 1 if (custom and not (stock_used or on_host) and stock_alt and nd.get("stock_obvious")) else 0
        elif nd["kind"] == "automation":
            met += 1 if any(len(stems(nd["need"]) & stems(x)) >= 2 for x in autos) else 0
        else:
            met += 1 if any(len(stems(nd["need"]) & stems(x)) >= 2 for x in rules) else 0
    ge = gold.get("entities") or []
    alts = " ".join(gold.get("acceptable_alternates") or [])
    invented = [("model", m) for m in models if not any(match(g["name"], m) for g in ge) and not match(m, alts)]
    excl = [x for x in (gold.get("exclusions") or []) + (gold.get("must_not_build") or [])
            if any(concept_in(x, m) for m in models + autos)]
    must_ask = any("must ask" in a for a in gold.get("ambiguity_points") or [])
    asked = r["kind"] not in {"diagnosis", ""}
    inv_score = sum(SEVERITY[k] for k, _ in invented) + SEVERITY["exclusion_violated"] * len(excl)
    rec_needs = [nd for nd in needs if nd["kind"] == "records" and nd.get("stock_obvious")]
    return {"need_coverage": met / len(needs) if needs else None,
            "reinvention_rate": reinvented / len(rec_needs) if rec_needs else None,
            "invented": [m for _, m in invented], "exclusions_violated": excl, "invented_severity": inv_score,
            "must_ask": must_ask, "asked": asked, "extension_models": exts,
            "custom_code_pieces": sum(1 for p in d.get("python_needed") or [] if p.get("delivery_lane") not in {"online_scheduled_action"}),
            **exclusion_pr(gold, d),
            **declined_named(gold, dict(d, integration_routes=d.get("integration_routes") or r.get("routes_nodesign") or [])),
            **s7_metrics(gold, r)}


def concept_in(concept, text):
    """Concept match, not a single shared stem: some '/'-alternative of the concept's head phrase
    has ALL its content stems in the text ('website/self-booking' does not match 'Rental Booking')."""
    head = concept.split("(")[0]
    alts = [a for a in re.split(r"[/,]| or ", head) if stems(a)]
    have = stems(text)
    return any(stems(a) <= have for a in alts)


def declined_named(gold, d):
    """Asked-for things that cannot be built: named in out_of_scope / notes / python_needed with a reason."""
    gd = gold.get("declined") or []
    blob = " ".join([str(r.get("item", "")) + " " + str(r.get("message", "")) for r in d.get("left_out") or []
                     if r.get("status") == "cannot"] + [str(x) for x in d.get("out_of_scope") or []] + [str(x) for x in d.get("notes") or []]
                    + [str(p.get("label", "")) + " " + str(p.get("reason", "")) for p in d.get("python_needed") or []]
                    + [str(r.get("item", "")) + " " + str(r.get("label", "")) for r in d.get("integration_routes") or [] if r.get("route") == "decline" and r.get("reason")])
    routes = d.get("integration_routes") or []
    gr = gold.get("routes") or {}
    got = {g: next((r.get("route") for r in routes if concept_in(g, str(r.get("service", "")))), None) for g in gr}
    return {"declined_gold": len(gd), "declined_named": sum(1 for g in gd if concept_in(g, blob)),
            "routes_gold": len(gr), "routes_correct": sum(1 for g, want in gr.items() if got[g] == want),
            "stock_custom_no_reason": sum(1 for c in d.get("stock_checks") or [] if c.get("custom_without_reason"))}


def exclusion_pr(gold, d):
    """Left out explicitly (design.left_out not put back, or out_of_scope copy) vs gold exclusions."""
    gold_x = list(gold.get("exclusions") or [])
    said = [r.get("item", "") + " " + r.get("quote", "") for r in d.get("left_out") or [] if not r.get("put_back")]
    said += [str(x) for x in d.get("out_of_scope") or []]
    hit = concept_in
    tp_p = sum(1 for x in said if any(hit(g, x) for g in gold_x))
    tp_r = sum(1 for g in gold_x if any(hit(g, x) for x in said))
    return {"excl_said": len(said), "excl_tp": tp_p, "excl_gold": len(gold_x), "excl_found": tp_r,
            "choices": len(d.get("checklist_choices") or [])}


_SNAP = []


def _snapshot():
    """One snapshot per eval process (bounded wait), reused for every design."""
    if not _SNAP:
        from app.db import SessionLocal
        from app.db_models import OdooConnection
        from app.odoo_snapshot import snapshot_for_connection

        with cf.ThreadPoolExecutor(1) as ex:
            def grab():
                with SessionLocal() as db:
                    return snapshot_for_connection(db.get(OdooConnection, CONN), "")
            try:
                _SNAP.append(ex.submit(grab).result(timeout=120))
            except Exception:  # noqa: BLE001
                _SNAP.append(None)
    return _SNAP[0]


def odoo_validity(design):
    """Deterministic admission (stage 2) against the live aonb snapshot."""
    try:
        from app.db import SessionLocal
        from app.db_models import OdooConnection
        from app.design_admission import SnapshotSchemaClient, validate_design
        from app.odoo_snapshot import snapshot_for_connection

        snap = _snapshot()
        if snap is None or not snap.ok:
            return {"ok": None, "error": "no snapshot"}
        res = validate_design(design, SnapshotSchemaClient(snap), major=snap.major,
                              hosting="online" if str(snap.series).startswith("saas") else "unknown",
                              edition=snap.edition, installed=set(snap.modules))
        return {"ok": res.ok, "errors": [e.code for e in res.errors], "major": snap.major}
    except Exception as exc:  # noqa: BLE001
        return {"ok": None, "error": str(exc)[:200]}




def s7_metrics(gold, r):
    """S7 scorer metrics: invention, violation severity, must-ask, stock conversion, cannot, routes."""
    d = r.get("design") or {}
    decision = r.get("diagnosis_decision") or {}
    # Prefer decision surfaces when design-less
    left = d.get("left_out") or decision.get("left_out") or []
    routes = d.get("integration_routes") or r.get("routes_nodesign") or decision.get("routes") or []
    checks = d.get("stock_checks") or decision.get("stock_checks") or []
    capability = decision.get("capability") or (d.get("meta") or {}).get("capability") or []
    models = [m.get("label") or m.get("name") for m in d.get("new_models") or []]
    autos = [a.get("label", "") for a in d.get("automations") or []]
    # unauthorized invention: custom model with no gold entity and no stock_obvious host
    ge = gold.get("entities") or []
    alts = " ".join(gold.get("acceptable_alternates") or [])
    invented = [m for m in models if not any(match(g["name"], m) for g in ge) and not match(m, alts)]
    unauth = invented  # same pool; rate over all custom models
    # exclusion violation severity (existing list + weight)
    excl = [x for x in (gold.get("exclusions") or []) + (gold.get("must_not_build") or [])
            if any(concept_in(x, m) for m in models + autos)]
    sev = SEVERITY["exclusion_violated"] * len(excl)
    # critical must-ask recall / unnecessary question rate
    must_ask = any("must ask" in a for a in gold.get("ambiguity_points") or [])
    asked = r.get("kind") not in {"diagnosis", ""}
    # stock conversion correctness: domain host converted vs generic host kept custom
    from app.ai_conversation.stock_routing import GENERIC_HOSTS, _is_generic, _is_domain
    # correct = the domain app holds it: converted from a custom copy, or no custom copy was made
    domain_ok = sum(1 for c in checks if c.get("choice") == "stock" and not c.get("custom_kept")
                    and _is_domain((c.get("use") or {}).get("model") or ""))
    domain_tot = sum(1 for c in checks if c.get("choice") == "stock" and _is_domain((c.get("use") or {}).get("model") or ""))
    generic_ok = sum(1 for c in checks
                     if (c.get("use") or {}).get("model") and _is_generic((c.get("use") or {}).get("model"))
                     and not c.get("converted"))
    generic_tot = sum(1 for c in checks
                      if (c.get("use") or {}).get("model") and _is_generic((c.get("use") or {}).get("model")))
    # cannot_fired: left_out status cannot OR capability decline OR route decline
    cannot = sum(1 for x in left if x.get("status") == "cannot")
    cannot += sum(1 for x in capability if x.get("decision") == "decline")
    cannot += sum(1 for x in routes if x.get("route") == "decline")
    # route persistence: gold routes present on design OR nodesign OR decision
    gr = gold.get("routes") or {}
    got = {g: next((rr.get("route") for rr in routes if concept_in(g, str(rr.get("service", "")))), None) for g in gr}
    return {
        "unauthorized_invention_rate": (len(unauth) / len(models)) if models else None,
        "exclusion_violation_severity": sev,
        "critical_must_ask": must_ask,
        "critical_must_ask_asked": bool(must_ask and asked),
        "unnecessary_question": bool(asked and not must_ask),
        "stock_domain_converted": domain_ok,
        "stock_domain_total": domain_tot,
        "stock_generic_kept": generic_ok,
        "stock_generic_total": generic_tot,
        "cannot_fired": cannot,
        "route_persisted": sum(1 for g, want in gr.items() if got[g] == want),
        "route_persisted_gold": len(gr),
    }

def config_fingerprint():
    from app.ai_conversation import app_design as ad

    blob = (ad.design_system_prompt(None) if hasattr(ad, "design_system_prompt") else "") + str(getattr(ad, "INTENT_CONTRACT_SYSTEM", ""))
    health = json.loads(u.urlopen(API + "/health", timeout=10).read())
    return {"model": health.get("ai_model_reasoning"), "provider": health.get("ai_provider"),
            "prompt_hash": hashlib.sha256(blob.encode()).hexdigest()[:16],
            "flags": {k: v for k, v in os.environ.items() if k.startswith("INGENIUM_")}}


PROVIDER_HOSTS = ("aiplatform.googleapis.com", "generativelanguage.googleapis.com")


def provider_reachable():
    """Preflight with no AI call: the API is up and the AI provider host resolves and accepts TCP."""
    import socket
    try:
        u.urlopen(API + "/health", timeout=10).read()
    except Exception as exc:  # noqa: BLE001
        return f"eval API {API} not reachable: {exc}"
    for host in PROVIDER_HOSTS:
        try:
            socket.create_connection((host, 443), timeout=8).close()
            return ""
        except OSError as exc:
            last = f"AI provider {host} not reachable: {exc}"
    return last


DETERMINISTIC_KINDS = {"stock_app_install"}


def provider_failed(r):
    """A row where the AI provider/network failed (no design, no AI call, or a request error)."""
    if r.get("kind") == "error":
        return True
    if r.get("kind") in DETERMINISTIC_KINDS:  # routes that answer without an AI call
        return False
    return not r.get("design") and not r.get("diagnosis_decision") and not (r.get("llm_calls") or 0)


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--metamorphic", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fresh", action="store_true", help="new sessions with no cached AI answers (sends x-ingenium-fresh)")
    a = ap.parse_args()
    global FRESH
    FRESH = FRESH or a.fresh
    if not CONN or CONN in FORBIDDEN_CONNECTIONS:
        sys.exit("set EVAL_CONNECTION to a disposable ingenium_* connection (the aonb connection is never used)")
    if a.split in ("holdout", "holdout_fresh") and os.environ.get("EVAL_UNSEAL") != "yes":
        sys.exit("holdout is sealed; set EVAL_UNSEAL=yes only for the final evaluation")
    cases = sorted((ROOT / a.split).glob("*.md"))
    if a.only:
        cases = [c for c in cases if c.stem in a.only.split(",")]
    jobs = [(c.stem, c.read_text(), rep, "base", "") for c in cases for rep in range(a.repeats)]
    if a.metamorphic:
        from metamorphic import variants

        for cid in a.metamorphic.split(","):
            for name, text, rel, changed in variants((ROOT / a.split / f"{cid}.md").read_text()):
                jobs.append((cid, text, 0, name, changed))
    why = provider_reachable()
    if why:
        sys.exit(f"ABORT preflight: {why}. No result written.")
    cfg = config_fingerprint()
    log = pathlib.Path(a.out + ".jsonl")
    results = [json.loads(x) for x in log.read_text().splitlines() if x.strip()] if log.exists() else []
    done = {(r["id"], r["rep"], r["variant"]) for r in results}
    jobs = [j for j in jobs if (j[0], j[2], j[3]) not in done]
    print(json.dumps({"resumed": len(results), "remaining": len(jobs)}), flush=True)
    streak = 0
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        _snapshot()
        futs = {pool.submit(run_case, cid, text): (cid, rep, var, ch) for cid, text, rep, var, ch in jobs}
        for f in cf.as_completed(futs):
            cid, rep, var, ch = futs[f]
            try:
                r = f.result()
            except Exception as exc:  # noqa: BLE001
                r = {"id": cid, "kind": "error", "error": str(exc)[:200], "design": None, "latency_s": None, "chars": 0}
            gold = yaml.safe_load((ROOT / a.split / f"{cid}.gold.yaml").read_text())
            r.update(rep=rep, variant=var, changed=ch, score=score(gold, r),
                     validity=odoo_validity(r["design"]) if r.get("design") else {"ok": None})
            r["design_summary"] = {"models": [m.get("label") for m in (r["design"] or {}).get("new_models") or []],
                                   "automations": len((r["design"] or {}).get("automations") or [])}
            r["validity_snapshot"] = "checked" if r["validity"].get("ok") is not None else "unchecked"
            pass  # design kept so runs can be re-scored offline
            streak = streak + 1 if provider_failed(r) else 0
            if streak > 3:
                why = provider_reachable() or "provider calls failing"
                pool.shutdown(wait=False, cancel_futures=True)
                sys.exit(f"ABORT: {streak} consecutive provider/network failures ({why}). "
                         f"Partial rows kept in {log} for inspection only; no summary written.")
            results.append(r)
            with log.open("a") as fh:
                fh.write(json.dumps(r, default=str) + "\n")
            print(json.dumps({"id": cid, "rep": rep, "variant": var, "kind": r.get("kind"), "lat": r.get("latency_s")}), flush=True)
    base = [r for r in results if r["variant"] == "base"]
    num = lambda k: [r["score"][k] for r in base if r["score"].get(k) is not None]  # noqa: E731
    lat = [r["latency_s"] for r in base if r.get("latency_s")]
    must = [r for r in base if r["score"]["must_ask"]]
    asked = [r for r in base if r["score"]["asked"]]
    meta = {}
    for cid in (a.metamorphic.split(",") if a.metamorphic else []):
        refs = [r["signature"] for r in base if r["id"] == cid and r.get("signature") is not None]
        floor = min((sig_similarity(a_, b_) for i, a_ in enumerate(refs) for b_ in refs[i + 1:]), default=1.0)
        for r in results:
            if r["id"] == cid and r["variant"] != "base" and refs:
                sim = max(sig_similarity(x, r.get("signature") or []) for x in refs)
                eq = r["variant"] in {"paraphrase", "irrelevant_insert"}
                meta[f"{cid}:{r['variant']}"] = {"signature_similarity": sim, "repeat_noise_floor": floor,
                                                  "expected": "equivalent" if eq else "changed",
                                                  "pass": (sim >= floor - 0.1) if eq else (sim < floor)}
    by_case = {}
    for r in base:
        by_case.setdefault(r["id"], []).append(r.get("signature") or [])
    summary = {
        "config": cfg, "split": a.split, "runs": len(base),
        "reached_diagnosis": sum(1 for r in base if r.get("kind") == "diagnosis"),
        "errors": sum(1 for r in base if r.get("kind") == "error"),
        "need_coverage_mean": round(statistics.mean(num("need_coverage")), 3) if num("need_coverage") else None,
        "reinvention_rate_mean": round(statistics.mean(num("reinvention_rate")), 3) if num("reinvention_rate") else None,
        "llm_calls_per_brief_mean": round(statistics.mean([r.get("llm_calls") or 0 for r in base]), 1) if base else None,
        "custom_code_pieces": sum(r["score"]["custom_code_pieces"] for r in base),
        "invented_severity_mean": round(statistics.mean([r["score"]["invented_severity"] for r in base]), 2) if base else None,
        "exclusion_violations": sum(len(r["score"]["exclusions_violated"]) for r in base),
        "exclusion_precision": (round(sum(r["score"].get("excl_tp", 0) for r in base) / max(1, sum(r["score"].get("excl_said", 0) for r in base)), 2)),
        "exclusion_recall": (round(sum(r["score"].get("excl_found", 0) for r in base) / max(1, sum(r["score"].get("excl_gold", 0) for r in base)), 2)),
        "declined_with_reason": f'{sum(r["score"].get("declined_named", 0) for r in base)}/{sum(r["score"].get("declined_gold", 0) for r in base)}',
        # N/A (None) when the split has no gold routes: nothing to be right or wrong about.
        "route_correctness": (round(sum(r["score"].get("routes_correct", 0) for r in base) / gold_routes, 2)
                              if (gold_routes := sum(r["score"].get("routes_gold", 0) for r in base)) else None),
        "stock_custom_without_reason": sum(r["score"].get("stock_custom_no_reason", 0) for r in base),
        "unauthorized_invention_rate": round(statistics.mean(num("unauthorized_invention_rate")), 3) if num("unauthorized_invention_rate") else None,
        "exclusion_violation_severity": sum(r["score"].get("exclusion_violation_severity", 0) for r in base),
        "critical_must_ask_recall": round(sum(1 for r in must if r["score"].get("critical_must_ask_asked")) / len(must), 2) if must else None,
        "unnecessary_question_rate": round(sum(1 for r in base if r["score"].get("unnecessary_question")) / len(base), 2) if base else None,
        "stock_domain_conversion": f'{sum(r["score"].get("stock_domain_converted", 0) for r in base)}/{sum(r["score"].get("stock_domain_total", 0) for r in base)}',
        "stock_generic_kept": f'{sum(r["score"].get("stock_generic_kept", 0) for r in base)}/{sum(r["score"].get("stock_generic_total", 0) for r in base)}',
        "cannot_fired": sum(r["score"].get("cannot_fired", 0) for r in base),
        "route_persistence": f'{sum(r["score"].get("route_persisted", 0) for r in base)}/{sum(r["score"].get("route_persisted_gold", 0) for r in base)}',
        "choices_per_brief": round(statistics.mean([r["score"].get("choices", 0) for r in base]), 2) if base else None,
        "question_recall": round(sum(1 for r in must if r["score"]["asked"]) / len(must), 2) if must else None,
        "question_precision": round(sum(1 for r in asked if r["score"]["must_ask"]) / len(asked), 2) if asked else None,
        "odoo_valid_rate": round(sum(1 for r in base if r["validity"].get("ok")) / max(1, sum(1 for r in base if r["validity"].get("ok") is not None)), 2),
        "validity_error_codes": sorted({c for r in base for c in r["validity"].get("errors") or []}),
        "latency_p50_s": pct(lat, 50), "latency_p95_s": pct(lat, 95),
        "tokens_estimate": int(statistics.mean([r["chars"] for r in base]) / 4) if base else None,
        "tokens_note": "estimate (chars/4 of brief+design); the provider does not report usage yet",
        "repeat_signature_similarity": {k: min((sig_similarity(a_, b_) for i, a_ in enumerate(vs) for b_ in vs[i + 1:]), default=1.0)
                                        for k, vs in by_case.items()},
        "metamorphic": meta,
    }
    import metrics as _fm  # fix-plan metrics: ITT coverage, micro invention, built vs suggested, 95% hierarchical CIs

    _rows = [_fm.run_metrics(yaml.safe_load((ROOT / a.split / f"{r['id']}.gold.yaml").read_text()), r) for r in base]
    summary["fixplan"] = {k: _fm.fmt(v) for k, v in _fm.summarize(_rows).items()}
    pathlib.Path(a.out).write_text(json.dumps({"summary": summary, "results": results}, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()

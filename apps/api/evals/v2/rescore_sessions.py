"""Re-score past runs offline (no AI calls) from the stored App Studio sessions in a time window.
usage: python evals/v2/rescore_sessions.py NAME START END RUN.json   (times ISO with offset)"""
import json, pathlib, statistics, sys, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
import yaml
from sqlalchemy import select
from app.db import SessionLocal
from app.db_models import AiSession
from evals.v2.score import score, find_design

name, start, end, run = sys.argv[1], dt.datetime.fromisoformat(sys.argv[2]), dt.datetime.fromisoformat(sys.argv[3]), sys.argv[4]
dev = pathlib.Path(__file__).parent / "dev"
briefs = {p.stem: p.read_text().strip() for p in dev.glob("*.md")}
gold = {p.name.split(".")[0]: yaml.safe_load(p.read_text()) for p in dev.glob("*.gold.yaml")}
res = []
with SessionLocal() as db:
    for s in db.execute(select(AiSession).where(AiSession.created_at >= start, AiSession.created_at < end)).scalars():
        po = " ".join((s.prompt_original or "").split())
        # base variant only: same opening and same length (+-3%); metamorphic variants differ
        bid = next((k for k, v in briefs.items()
                    if " ".join(v.split())[:60] == po[:60] and abs(len(" ".join(v.split())) - len(po)) <= 0.03 * len(po)), None)
        only = set(sys.argv[5].split(",")) if len(sys.argv) > 5 else None
        if not bid or (only and bid not in only):
            continue
        conv = json.loads(s.conversation_json or "[]")
        pend = json.loads(s.pending_clarification_json or "null") or {}
        design = find_design(conv)
        kind = pend.get("kind") or ("diagnosis" if design else "")
        r = {"design": design, "kind": kind}
        res.append((bid, kind, score(gold[bid], r)))
base = [x for x in res]
sc = [x[2] for x in base]
must = [x for x in base if x[2]["must_ask"]]
asked = [x for x in base if x[2]["asked"]]
summ = json.load(open(run))["summary"]
out = {
    "run": name, "sessions": len(base), "briefs": len({b for b, _, _ in base}),
    "diagnosis_rate": round(sum(1 for _, k, _ in base if k == "diagnosis") / max(1, len(base)), 2),
    "coverage": round(statistics.mean([s["need_coverage"] for s in sc if s["need_coverage"] is not None]), 3),
    "excl_precision": round(sum(s["excl_tp"] for s in sc) / max(1, sum(s["excl_said"] for s in sc)), 2),
    "excl_recall": round(sum(s["excl_found"] for s in sc) / max(1, sum(s["excl_gold"] for s in sc)), 2),
    "violations": sum(len(s["exclusions_violated"]) for s in sc),
    "declined_named": f'{sum(s["declined_named"] for s in sc)}/{sum(s["declined_gold"] for s in sc)}',
    "q_recall": round(sum(1 for x in must if x[2]["asked"]) / len(must), 2) if must else None,
    "q_precision": round(sum(1 for x in asked if x[2]["must_ask"]) / len(asked), 2) if asked else None,
    "valid(run)": summ.get("odoo_valid_rate"), "calls(run)": summ.get("llm_calls_per_brief_mean"),
    "p95(run)": summ.get("latency_p95_s"),
    "reinvention": round(statistics.mean([s["reinvention_rate"] for s in sc if s.get("reinvention_rate") is not None] or [0]), 3),
}
print(json.dumps(out))

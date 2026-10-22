"""Contract-stage experiment: contract call (role tag) -> design call -> downstream, authorizer off vs on (shadow).
2 LLM calls per run, no Odoo access. Rows -> OUT.jsonl; summary with false_fold_rate + invention CIs."""
import concurrent.futures as cf, json, os, pathlib, random, sys, statistics, threading

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
os.environ.setdefault("INGENIUM_BRIEF_CHECKLIST", "1")
import yaml  # noqa: E402
import metrics, score  # noqa: E402
from replay import downstream  # noqa: E402

BRIEFS = sys.argv[1].split(",")
N = int(sys.argv[2])
OUT = pathlib.Path(sys.argv[3])
lock = threading.Lock()


def run(b):
    from app.ai_client.ai_scope import ai_scope
    from app.ai_conversation import app_design as ad, brief_checklist as bc
    from app.ai_conversation.intent_contract import normalize_intent_contract
    from app.llm_provider import get_llm_provider_for_tier

    brief = (HERE / f"{b}.md").read_text()
    prov = get_llm_provider_for_tier("contract") or get_llm_provider_for_tier("fast")
    fast = get_llm_provider_for_tier("fast")
    with ai_scope(db="fp_contract_exp", fresh=True, surface="internal"):
        user = ad.intent_contract_user_prompt(brief) + ("\n\n" + bc.CONTRACT_ADDENDUM if bc.enabled() else "")
        raw = ad._parse_json(prov.generate_json(user, system=ad.intent_contract_system_prompt(), timeout_s=180.0, temperature=0.0)) or {}
        contract = normalize_intent_contract(raw.get("requirements") or [], brief, trusted=False)
        d_raw = ad._parse_json(fast.generate_json(ad.design_user_prompt(brief, budget=ad.model_budget_for(brief), intent_contract=contract),
                                                  system=ad.design_system_prompt(None), timeout_s=180.0, temperature=0.2)) or {}
    d_raw["intent_contract"] = contract
    return {"brief": b, "contract_roles": [(r.get("subject"), r.get("kind"), r.get("role")) for r in contract],
            "off": downstream(d_raw, brief, "off"), "on": downstream(d_raw, brief, "on")}


rows = [json.loads(l) for l in OUT.read_text().splitlines()] if OUT.exists() else []
need = [b for b in BRIEFS for _ in range(max(0, N - sum(1 for r in rows if r["brief"] == b)))]
with cf.ThreadPoolExecutor(4) as pool:
    for f in cf.as_completed([pool.submit(run, b) for b in need]):
        try:
            r = f.result()
        except Exception as exc:  # noqa: BLE001
            print("ERR", str(exc)[:200], flush=True); continue
        with lock, OUT.open("a") as fh:
            fh.write(json.dumps(r, default=str) + "\n")
        print(r["brief"], [m["label"] for m in r["off"]["new_models"]], "->", [m["label"] for m in r["on"]["new_models"]], flush=True)

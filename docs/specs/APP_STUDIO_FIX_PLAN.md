# App Studio fix plan (from Claude Sonnet 5 review of APP_STUDIO_HANDOFF.md, 2026-10-19; approved by Tope)
Assumed shapes (e.g. Requirement{id,spans,decision}) must be verified against code.

## Diagnosis
- Failure A (detail->new model) = control problem: prompt licenses gap-fill ("fill obvious gaps... supporting models", example list "rules, risks, plans, configuration", suggested:true as hedge); every post-LLM step is additive (strengthen_design, ensure_jobs, complete_from_brief, _cover_sections); contract has decision but no entity-vs-attribute role; budget 3-12 from brief length acts as quota. Sampling amplifies (candidate set stable, promoted subset flips).
- Current numbers can't steer: n=7 single run, SE~0.19 (CI ±0.37); 0.333->0.433 is noise; h-fix worked (terse_inventory 0). Ratio-of-ratios punishes small designs. Survivorship: coverage/invention over reached briefs only -> report intent-to-treat (unreached = coverage 0). Holdout is burnt (examples came from it) -> becomes dev2; build fresh holdout.

## Discriminating experiments (design stage only, contract frozen, ~10 runs/cell, 3 failing briefs)
1 budget removed/=1 vs current; 2 gap-fill sentence deleted; 3 temperature default vs low.

## (a) Prompt + schema
Replace gap-fill sentence and "suggested true" instruction with:
```
NEW MODELS — HARD RULES
1. A new x_* model is a table whose rows the owner will create and look back at on their own.
   Create one only when the owner's words show that (see "evidence").
2. Everything else is a FIELD on a record already in the design:
   - a "which ___", "type of ___", "per ___", or any label the owner groups reports by
     -> a field: many2one to an installed stock model if one truly fits, else a selection
        if the owner listed the values, else a char. Never a new model.
   - something mentioned once as background (what the business is or owns) -> nothing.
   - something the owner marks maybe / later / future / someday -> not built; put it in left_out.
3. Do not add catalog, schedule, log, share, rule or configuration models the owner did not describe,
   and never because they "would be useful". Missing views, menus and fields on the owner's own
   records are yours to fill. Missing models are not.
4. If unsure between a field and a model, choose the field and say in "fold_note" what the owner
   could say to get a model.
5. The number of new models equals the number of different things the owner wants to keep rows of.
   There is no minimum.
For each new model write "evidence" FIRST, before any other key:
  "evidence": {"quote": <verbatim owner phrase showing they keep rows of this thing>,
    "owner_fields": [<verbatim facts owner wants recorded ABOUT THIS THING>],
    "role": "main_record" | "own_records" | "line_of:<model>"}
If you cannot copy a quote, do not output the model.
Also output "folded": [{"concept","quote","as":"many2one|selection|char","on":<model>}]
for every noun you decided NOT to make a model. "why" must paraphrase the owner, not describe features.
```
- Add DesignModel.evidence, AppDesign.folded, python_needed[].kind enum {computed_field, scheduled_action, onchange, constraint, external_call}.
- Contract: Requirement.role ∈ {record, attribute, dimension, context, future, rule, access} (one enum on existing call, no extra call).
- Budget = n_record_requirements + 1, no floor, no length term.
- Few-shot: contrastive pairs from domains absent from all eval splits (e.g. bakery: "which flavour" folded vs "flavour list with a price each" kept); keep a manifest so evals never reuse them.
- Structured output: provider JSON schema, explicit property order if supported, seed if exposed; check Gemini temperature guidance.
- Flip `suggested`: suggested = NOT built, owner opts in.

## (b) Authorizer: apps/api/app/ai_conversation/model_authorizer.py (pure, no I/O/LLM; idempotent, order-independent, never adds a model; bias to fold; no English cue lists — lexical judgments come from LLM roles with verified spans; code only verifies spans/structure; briefs are code-switched e.g. Pidgin)
Quote counts only if verbatim substring of source_brief AND shares label tokens with model (language-agnostic: any label token).
Own attributes = verbatim owner phrases stem-overlapping one of the model's own field strings; each phrase credited to exactly ONE model (best field match) — blocks laundering.
Verdicts in order:
0 owner promoted in UI -> keep
1 spans overlap contract left_out/future -> suggest (not built)
2 no verified bound quote and no contract span -> drop
3 contract role record and (LLM role main_record or >=1 own attr) -> keep
4 >=2 own attrs and contract role not attribute/dimension -> keep
5 LLM role line_of:*, single parent, inverse m2o, >=1 own attr -> keep as line
6 no field in design points at it -> drop (orphan)
7 else fold onto referencing host: stock m2o if grounding hit is INSTALLED, score>=0.8, not lexical-only; else selection if owner listed >=2 values; else char.
apply_calls: rewrite referencing fields (o2m/m2m to folded/dropped removed; m2o -> stock m2o/selection/char), preserve lineage/string/required; prune menus (empty parents), record_rules, automations (retarget first if owner span), security_groups access, python_needed mentions, relations; append folded notes (stash full DesignModel in hidden folded[].proposal so Promote restores with no LLM call) and suggested notes to left_out; model_budget = max(1, len(new_models)).
Reference code (Claude's sketch):
```python
def authorize_models(design, *, brief, contract, grounding, snapshot, force_keep=frozenset()):
    brief_n = norm(brief)
    info = {m.name: _gather(m, brief_n, contract) for m in design.new_models}
    _credit_each_owner_phrase_once(info, design)
    calls = [_decide(m, info[m.name], design, contract, brief_n, grounding, snapshot, force_keep)
             for m in sorted(design.new_models, key=lambda m: m.name)]
    return AuthResult(calls)
def _gather(m, brief_n, contract):
    ev = getattr(m, "evidence", None) or {}
    reqs = [r for r in contract.requirements if r.id in m.requirement_ids]
    bound = verbatim(ev.get("quote", ""), brief_n) and bool(stems(m.label) & stems(ev["quote"]))
    own = {norm(q) for q in ev.get("owner_fields", []) if verbatim(q, brief_n) and any(stems(f.string) & stems(q) for f in m.fields)}
    return dict(ev=ev, anchored=bound or any(r.spans for r in reqs), own=own, roles={r.role for r in reqs}, spans=[s for r in reqs for s in r.spans])
```
norm = casefold, NFKD, [a-z0-9]+ tokens, drop per-locale fillers; stems = 5-char prefix (reuse clause_grounding stemmer).
Integration in build_app_design: after LLM + validate_and_repair -> authorize_models(force_keep=session.promoted_models) -> apply_calls -> if touched re-run validate_and_repair(strict_refs=True; dangling refs -> left_out, never silent) -> authorize_python -> strengthen_design (templates only on kept models) -> existing dedupe/ensure_jobs/complete_from_brief/scope_and_limits -> assert_invariants (every new_model has keep verdict + lineage else demote+log).
Outline-derived models (_merge_outline, _cover_sections): give requirement_ids to an outline requirement with spans so rule 2 passes.
Owner notes via assumptions list (silent drops telemetry only): fold "I kept **Service** as a simple choice on each appointment instead of a separate list. Want to manage services (prices, how long each takes)? *Add a Services list*." suggest "You said loyalty points can wait. I haven't built them."

## D/C shared cause: conservation law
Precision audit: no element without lineage to a requirement whose decision licenses it. Recall audit: no in-scope requirement without a realizing element.
- authorize_python: keep python_needed item only if kind==scheduled_action or a linked requirement decision==option_a; else realize declaratively (count/sum/avg -> pivot/graph measure, list sum, group-by; latest -> related field) + plain note. Live count on parent form needing computed field on metadata-only lane -> left_out as declined/deferred, not silent.
- Coverage: audit misses (~60 needs) as unreached / scorer-miss / true miss first. Host-fit check: reject stock host when its required fields can't be satisfied from brief (e.g. fleet.vehicle.log.fuel needs vehicle) or its app isn't installed on the connection. Orphan-requirement repair: one targeted LLM call only for unrealized requirements.
- Latency: if critic flags aren't consumed, drop the critic (~1 of 3.2 calls); pruning before strengthen_design saves reads.

## (c) Eval changes
1 Record & replay: store raw contract + pre-authorizer design JSON, k=5/brief; run authorizer+downstream offline (zero LLM cost, paired exact deltas). Only prompt changes need fresh sampling.
2 Common random numbers: seeds hash(brief_id, repeat), same for both arms.
3 Stats: k>=5, hierarchical bootstrap (briefs, then repeats), paired-difference CI (~±0.09 at 28x5).
4 Families: 3-4 variants per gold brief (terse, voice, rambling, code-switched Pidgin/Yoruba/Hausa); metric model_set_stability = mean pairwise Jaccard of aligned model sets.
5 Alignment: Hungarian (scipy linear_sum_assignment) design models<->gold entities on name n-grams + attribute overlap + span overlap (add spans: to gold files); judge only ambiguous pairs, cached, local Qwen3 (not generator), calibrate on ~40 hand labels, report kappa.
6 Metrics: ITT coverage; invention as counts + micro-average with CI; built vs folded/suggested separately; false_fold_rate; promote_recoverable; attribute-need met if matching field exists on matched entity (custom or stock ext).
7 New holdout 12-15 briefs, authored blind to failures, stratified by domain + code-switching, hash-frozen, once per release. Current holdout -> dev2; unseen 3 = smoke.

## Verification
Unit: keep "for every client we keep a service history: each service done, the date, the price, notes" (Service Record); keep "We have a list of our services, each with a price and how long it takes"; fold salon_voice service, ngo_rambling pack type & community; drop Stylist Schedule, Generator Log, Resident Share; suggest no_repair_maybe Loyalty Account; laundering (real quote not bound to label) -> drop; overclaim main_record without contract record role falls to own-attr test.
Property/metamorphic: idempotent, order-independent, never adds; 0 dangling refs after apply_calls; lineage preserved; domain noun swap (salon->garage, stylist->mechanic, service->part) and filler/code-switch injection don't change verdicts.
Regression on recorded designs: invented total only down; per-brief ITT coverage drop >0.05 on at most one brief; false_fold_rate <=0.10.
Expected (unmeasured estimates): invention 0.43->0.10-0.20; severity 1.88->0.4-0.8; exclusion recall stays 1.0; coverage >=0.53; custom code 2->0; stability >=0.85; calls 3.2->2.2-3.0.

## Order
1 metric fixes + record/replay, re-baseline k=5; 2 authorizer offline on recordings; 3 schema+prompt, then the 3 experiments; 4 python gate + orphan repair; 5 shadow mode on real sessions ~1 week (log verdicts, Promote clicks measure false folds); 6 fresh holdout before claiming results.
Unrelated: JSON-2 422 on res.partner/create missing vals_list — JSON-2 create takes named vals_list (list of dicts), not execute_kw single vals; fix payload shape.

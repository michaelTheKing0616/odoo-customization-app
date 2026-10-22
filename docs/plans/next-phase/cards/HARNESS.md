# Cards — Harness (continuous eval, judge, shadow)

Cross-cutting. Not a UI track and not a replacement for Track 1 goldens, Document-12-style self-critique (`T8-CRITIC`), or the T8 scenario runner (`T8-EV-HARNESS`). One eval store. If `eval_run` tables appear from T8 first, these cards extend them.

**Categories (reuse, do not invent a second taxonomy):** `golden`, `adversarial`, `ambiguity`, `version_drift`, `cost`, `safety`.

**Lock:** no live LLM call in a PR-blocking test. A PR runs active cases as property checks and cassettes. Live generation, the judge, and shadow calls run nightly or in a bounded pre-release window.

**Shared do-not:** do not weaken a lock in `../01`; no secrets in case payloads or judge prompts; a candidate never gates CI; do not replace inline self-critique with the judge; do not serve shadow output to a user; do not run two judges of the same model family grading each other when a stronger different provider is configured; shadow windows are bounded (duration and call cap recorded before the run).

**Schema (copied):** `eval_case` fields: `id`, `input`, `context`, `expected_properties`, `category`, `source` (`production_failure` | `user_flag` | `low_confidence_trigger` | `manual_addition` | `synthetic`), `added_date`, `status` (`candidate` | `active` | `retired`), `reviewed_by`. `expected_properties` are invariants ("no field outside this set"), not one exact string.

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_eval_harness.py
```

---

### H1 — Eval case schema and capture
- **Status:** OPEN. **depends_on:** one existing negative gate (T1-F0, a Bridge tier test, or a worker-bot refusal). Capture hooks attach to gates that already exist; missing gates are skipped, not invented here.
- **Pressure:** C2 U1 F2 K2 V1 I1 +0 = 9 → Grok standard
- **Change:** `apps/api/app/evals/` (new), migration for `eval_case`, hook helper `capture_candidate(...)`.
- **Acceptance:** [ ] a forced failure in one existing gate writes a `candidate` in the same test run; [ ] payload has input and context enough to replay; [ ] no secret keys in the stored JSON.
- **Negative:** the same failure twice does not insert two rows (idempotent on input hash + gate id).

### H2 — Review queue and versioning
- **Status:** OPEN. **depends_on:** H1
- **Pressure:** 8 → Grok standard
- **Change:** review API plus a minimal queue UI or CLI. Promotion writes `reviewed_by` and a reason. Retirement is the same discipline in reverse.
- **Acceptance:** [ ] promote and discard record a reason; [ ] an unreviewed row cannot become `active`; [ ] the active set's history is readable (who changed which case, when).
- **Negative:** a client-supplied `reviewed_by` is ignored; the server uses the authenticated user.

### H3 — CI and nightly
- **Status:** OPEN. **depends_on:** H2, T1-F1, T1-F2
- **Pressure:** C2 U1 F2 K2 V2 I1 +0 = 10 → Grok high
- **Acceptance:** [ ] Maintenance and Service-cards are the first two `active` cases, not a second runner; [ ] a PR that breaks an active case's `expected_properties` fails CI without a live model call; [ ] nightly job runs the full active set and writes a result row; [ ] when the active set exceeds the size recorded in this card's build log (start at 40), PR runs a fast subset and nightly runs the full set.
- **Negative:** a `candidate` row does not fail CI.

### H4 — Judge sampling and trends
- **Status:** OPEN. **depends_on:** H3, T8-GW-REG (model registry). Not a PR gate.
- **Pressure:** C2 U2 F2 K2 V2 I1 +0 = 11 → Grok high
- **Acceptance:** [ ] a scheduled sample of Generate, Expert, Dashboard Studio, and Worker Bot outputs is scored on correctness, completeness, citation, tone, and hallucination ("claim traces to a retrieved or generated source"); [ ] the judge is a different, stronger registry entry than the generator when one exists; [ ] scores are stored per dimension with judge model id and date; [ ] a known-bad fixture scores below the pass line on correctness.
- **Do not:** alert on one sample. Alert only after two periods of trend data (DoD item 4).

### H5 — Judge calibration
- **Status:** OPEN. **depends_on:** H4. **Pressure:** 9 → Grok standard. Operator supplies the human labels.
- **Acceptance:** [ ] one human-vs-judge agreement rate is written to the progress log before any judge score gates a rollout; [ ] a dimension below the recorded agreement floor gets one prompt revision and a second measurement.

### H6 — Shadow mode
- **Status:** OPEN. **depends_on:** H4 and a swappable provider in `llm_gateway` (in-house; ADR-02 may stay open).
- **Pressure:** C2 U2 F3 K2 V2 I1 +0 = 12 → Grok high, plus a reviewer
- **Acceptance:** [ ] candidate config runs beside production for a capped window; [ ] the HTTP response to the user is the production output (asserted by reading the response, not only the code); [ ] both outputs are stored and scored; [ ] a worse candidate is reported before any canary; [ ] the window's token cost is measured and written to the progress log.
- **Negative:** shadow route has no path that returns the candidate body.

### H7 — Canary and auto-rollback
- **Status:** OPEN. **depends_on:** H5, H6
- **Pressure:** 12 → Grok high, plus a reviewer
- **Acceptance:** [ ] rollout is a percentage, default 0; [ ] a regressed canary trips a documented threshold and pauses itself with no operator click; [ ] pause stops new assignments within one request cycle.
- **Negative:** a human-only "please check the graph" trigger does not count.

### H8 — End-to-end proof
- **Status:** OPEN. **depends_on:** H3, H5, H7. **Pressure:** 10 → Grok high
- **Acceptance:** [ ] one injected regression is captured, scored, shadowed, canaried, and auto-rolled back; [ ] one genuine improvement completes rollout to 100%; [ ] both outcomes are in the progress log. An agent may not check this card done from a fixture run that never assigned real traffic to the canary.

**DoD map:** H1–H2 cover spec items 1 and 9 (taxonomy). H3 covers 2 and 3. H4 covers 4. H5 covers 5. H6 covers 6 and 10. H7 covers 7. H8 covers 8.

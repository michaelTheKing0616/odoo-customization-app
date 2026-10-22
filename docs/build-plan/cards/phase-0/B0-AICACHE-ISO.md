# B0-AICACHE-ISO: no test reads ~/.ingenium; no test reaches Vertex unless live_ai (skipped)

ID: B0-AICACHE-ISO
Title: no test reads ~/.ingenium; no test reaches Vertex unless live_ai (skipped)
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-2-AC4;CACHE-B
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- `sed -n '469p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- handover list line (context, not an AC): INGENIUM_MASTER_HANDOVER.md L469
- apps/api/tests/conftest.py
- apps/api/app/ai_draft_cache.py
- apps/api/app/ai_client/
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/conftest.py
- apps/api/app/ai_draft_cache.py
- apps/api/app/ai_client/
- apps/api/tests/test_b0_aicache_iso.py (new)
Goal: Make every AC below true for `B0-AICACHE-ISO` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. List the behaviours under test, one per AC, with concrete input → expected output.
2. Write the tests in the allow-list files. Each test must fail if the behaviour were removed: name in the Worker packet the product line whose deletion would make it fail.
3. Run the Test plan command twice (second time `-p randomly` for API once DEC-047 lands) → identical green results.
4. If a test exposes a real defect, do not fix product code: mark it `xfail(strict=True, reason=<new ledger row>)` and report it in the Worker packet.
5. Write the Worker packet.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: exact-response cache keyed model+prompt+inputs+snapshot hash; TTL; invalidation (source: ledger CACHE-B, BRIDGE_RUNNER_SPEC LLM caching (b); GAP §3)
Symbols:
- `make_key(*, provider, model, method, system, prompt, options, db, odoo_version, snapshot_hash)`, `get_exact(key)`, `put(..., ttl_s=None)`, `invalidate_db(db)`, `note_snapshot(db, snapshot_hash)`, `DEFAULT_TTL_S` (7 days when `db` is set), `VERSION_ONLY_TTL_S` (90 days when `db` is empty), `_path()` in `apps/api/app/ai_client/ai_cache.py`. `_path()` reads `INGENIUM_AI_CACHE_PATH`, otherwise `~/.ingenium/ai_cache.sqlite`.
- `save_draft_cache` in `apps/api/app/ai_draft_cache.py` stores a draft by `connection_id` plus prompt hash. That store is not this exact-response cache.
Worked example:
- Set `INGENIUM_AI_CACHE_PATH` to a temp sqlite file. `key, scope = make_key(provider="mock", model="m", method="complete", system="", prompt="hello", options={"n": 1}, db="ingenium_x", odoo_version="19", snapshot_hash="snap-a")`. `put(key, scope, db="ingenium_x", model="m", prompt="hello", value="ANSWER", ttl_s=60)` → `get_exact(key)` is `"ANSWER"`. The same arguments with `snapshot_hash="snap-b"` make a different key, and `get_exact` of that key is `None`. `invalidate_db("ingenium_x")` → `get_exact(key)` is `None`. A row whose `expires` is already past → `get_exact` returns `None`.
Decision:
| state | result |
| key matches, `expires` is in the future, deps fresh | cached value |
| model, prompt, options, or `snapshot_hash` differs | miss (`None`) |
| `expires` is in the past | `None` |
| `invalidate_db(db)` | a later `get_exact` for that db is `None` |
| `note_snapshot(db, new_hash)` and a previous hash exists | returns True; `mark_changed(db, [ALL])` makes whole-DB entries stale |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_aicache_iso.py` → all pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.

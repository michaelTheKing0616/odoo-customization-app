# Cards — T4 compiler, MCP, dashboards, offline, models, skills/triggers

Self-contained. Gates and compiler DoD 1–20: `../T4_COMPILER_MCP_DASH_OFFLINE_MODELS.md`. The compiler build spec's phase order wins over the conceptual order. Master order wins over the MCP research order (progress + MCP, then Dashboard, then Offline). MCP is read-only from Ingenium (master Track 5).

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; no customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests; stay inside "Change". **T4-specific:** no write-effect call through an MCP client, and no `call_model_method`-style tool inside the Ingenium process (stop-ship); YOLO MCP mode is never used in production; ISPEC does not start before Track 1 is done; `ModuleSpec` stays the sole module IR (ISPEC serializes it); Recompile never overwrites in place; Stage H human review always runs for wireframe output; no code path treats "a trigger exists" as pre-approval (stop-ship, R-07); promote is never flushed automatically from the offline queue; D8 is open, so the gateway card documents and does not pick LiteLLM; no hard-coded model id, price, or context window outside the model registry; Bucket C (full WYSIWYG spec editor, multi-modal Sources beyond documents, cross-project Skills) is not built this phase.

**Bucket B (new, default off until its confirm gate exists):** Recompile (confirm + diff), Sync (confirm + drift report; drift blocks), Recompile with another provider (new versioned artifact), Write a Skill (confirm + blast radius), Trigger (creation confirmed once; each firing uses the approval gate).

**Code today:** `apps/api/app/progress/stage_bus.py` (`StageBus`, 23 lines; `test_events_are_stage_accurate`, `test_spinner_is_not_a_stage`); `apps/api/app/offline/idempotency.py` (`MemoryIdempotencyStore`, `claim_db`; `test_idempotency_store.py`); `apps/api/app/mcp_guard.py` (`test_mcp_read_is_allowed`, `test_mcp_write_is_refused`, `test_trigger_existence_is_not_approval`); `apps/api/app/llm_gateway/` (see `T8_ENGINE_CORE.md`). No IndexedDB, ULID, ISPEC, or Dashboard Studio code exists.

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_stage_bus.py tests/test_idempotency_store.py tests/test_mcp_guard.py tests/test_no_mcp_write.py
pnpm --filter @odoo-custom/web test -- <path>
pnpm --filter @odoo-custom/web test:e2e e2e/<spec>.ts
```

**Audit events:** `tool_call` (MCP reads), `change`, `module` (recompile artifacts), `apply`, `note` (trigger fired, with the person and plan hash).

---

### T4-PROG — Live progress on four surfaces (6.1, compiler DoD 8–10, master DoD 7)
- **Status:** SEEDED (server-side `StageBus`). The four web surfaces still use generic spinners in places.
- **depends_on:** none
- **Pressure:** C3 U1 F1 K2 V2 I0 +0 = 9 → Grok standard
- **Read first:** `progress/stage_bus.py`; web: `apps/web/src/app/connections/[id]/studio/page.tsx`, `…/bulk-suite/page.tsx`, `apps/web/src/components/expert/`, any dashboard surface; `rg -n "Spinner|animate-spin" apps/web/src`.
- **Steps:** (1) emit named stages from generation, Dashboard Studio, Expert, and bulk operations; (2) stream them (SSE or polling) to a shared `StageProgress` component; (3) technical detail behind a "Show details" disclosure, closed by default; (4) a tool-call limit asks "Continue or stop?" and never continues silently.
- **Acceptance:** [ ] four surfaces stage-accurate; [ ] `rg -n "animate-spin" ` on those four files returns nothing; [ ] detail is opt-in; [ ] tool-call limit prompt exists on every long surface.
- **Negative:** a stage event with an unknown name fails the bus test.

### T4-MCP0 — MCP Phase 0 hands-on
- **Status:** OPEN (research card)
- **Pressure:** 5 → cheap / operator
- **Acceptance:** [ ] search and aggregate return correct rows on a test database; [ ] YOLO versus standard permission difference observed and written in the progress log; [ ] YOLO marked never-in-production.

### T4-MCP1 — MCP Phase 1 read-only
- **Status:** PARTIAL (O20-09 native-absent detection exists in the package).
- **depends_on:** T2-J1, T4-MCP0
- **Pressure:** C2 U2 F2 K2 V2 I1 +0 = 11 → Grok high effort
- **Acceptance:** [ ] master DoD 8: detect native `mcp_server` when present and prefer it for reads; [ ] smart field selection, default cap 15 fields, payload reduction measured; [ ] aggregation on 19+ matches older majors; [ ] JSON-2 appears in request logs on 19+.
- **Negative:** an MCP tool whose name implies write (`create`, `write`, `unlink`, `call_model_method`) is never registered.

### T4-MCP5 — MCP Phase 5 research close
- **Status:** OPEN
- **Pressure:** 3 → cheap
- **Acceptance:** [ ] fresh-instance dashboard session, BYOK question, and competitive comparison written; no new product surface.

### T4-DASH — AI Dashboard Studio (6.3, master DoD 9)
- **Status:** OPEN
- **depends_on:** 5A-01, T4-MCP1, UI-F09 (motion), D12 `recharts`
- **Pressure:** C3 U2 F2 K2 V2 I1 +0 = 12 → Grok high effort
- **Change:** new `apps/api/app/routers/dashboards.py`, table `dashboards` (migration), web `apps/web/src/app/studio/dashboards/page.tsx`.
- **Acceptance:** [ ] a dashboard is produced, persisted on the project, and every figure cites its query; [ ] a protected model (`account.move`, `hr.payslip`, …) is declined or linked, not queried around; [ ] the guardrail has a test, not only a design.
- **Negative:** a prompt asking for payroll totals returns a refusal card.

### T4-OFF — Offline queue (6.4, master DoD 10)
- **Status:** SEEDED (server `IdempotencyStore`). No client queue.
- **depends_on:** 5A-02
- **Pressure:** C3 U2 F3 K2 V2 I1 +0 = 13 → Grok high effort
- **Change:** web `apps/web/src/lib/offline/queue.ts` (IndexedDB), ULID keys, exponential backoff; API: every queued route claims the key through `claim_db`.
- **Acceptance:** [ ] a simulated dropped ack does not double-apply (E2E step 5); [ ] the queue survives reload and a second tab; [ ] a queued promote still requires a human confirm and is never flushed automatically.
- **Negative:** two tabs flushing the same item produce one server effect.

### T4-ISPEC — ISPEC round-trip (6.5, compiler DoD 1–2)
- **Status:** OPEN
- **depends_on:** T1-F2 (Track 1 done)
- **Pressure:** C3 U2 F3 K2 V2 I2 +0 = 14 → frontier
- **Acceptance:** [ ] lossless round-trip ModuleSpec → ISPEC → ModuleSpec on complex fixtures (property test over the golden specs); [ ] ModuleSpec remains the sole IR.

### T4-SYNC — Recompile and Sync (compiler DoD 3–5, master DoD 11)
- **Status:** OPEN
- **depends_on:** T4-ISPEC
- **Pressure:** C3 U2 F3 K3 V2 I2 +0 = 15 → frontier + reviewer
- **Acceptance:** [ ] recompile writes a new versioned artifact; the previous artifact remains; [ ] drift (spec edited outside, or module edited in Odoo) blocks Sync with a report; [ ] another provider yields a distinct versioned artifact.
- **Negative:** recompile with an identical spec into an existing version path is refused.

### T4-BROWSER — Browser-testing sub-agent in Stage F (compiler DoD 6–7, master DoD 12)
- **Status:** OPEN
- **depends_on:** T4-ISPEC
- **Pressure:** 11 → Grok high effort
- **Acceptance:** [ ] the agent runs inside Stage F; [ ] it catches at least one defect class Python-only tests miss, recorded with the module and the defect; [ ] false-positive rate written down.
- **Do not:** claim the gate without a caught defect.

### T4-WIRE — Wireframe to app (6.6, compiler DoD 12, master DoD 13)
- **Status:** OPEN
- **depends_on:** T1-F2
- **Pressure:** 11 → Grok high effort
- **Acceptance:** [ ] a real sketch becomes a spec; ambiguity becomes a clarify step; [ ] code-inspection test shows Stage H cannot be bypassed (exactly one path from wireframe to apply, and it passes Stage H).

### T4-LLM3 — Three-tier provider abstraction (6.7, master DoD 14)
- **Status:** SEEDED by the gateway (`llm_gateway/adapters/anthropic.py`, `openai.py`, `gemini.py`, `fallback.py`, `registry.py`). ADR-02 (D8) open.
- **depends_on:** ADR-02
- **Pressure:** 9 → Grok standard
- **Acceptance:** [ ] swappable: one test switches provider with no change above the gateway; [ ] frontier adapter inactive by default; [ ] existing Gemini and Qwen paths keep working; [ ] no model id outside the registry (`rg` test).
- **Stop:** if D8 is still open, do not pick LiteLLM; document only.

### T4-SKT — Skills, Sources, Triggers (6.8, compiler DoD 15–18, master DoD 15) — stop-ship
- **Status:** SEEDED (`test_trigger_existence_is_not_approval`).
- **depends_on:** 5A-04, T6-04
- **Pressure:** C3 U2 F3 K3 V2 I3 +0 = 16 → frontier + reviewer
- **Acceptance:** [ ] no code path treats a trigger's existence as pre-approval; each firing re-enters the approval gate and creates a new plan card; [ ] protected models blocked; [ ] a Community trigger works without Enterprise; [ ] audit names the trigger, the person, and the plan hash.
- **Negative:** fire a trigger twice; two separate approvals are required; a code-inspection test asserts no call from the trigger runner to `executor.apply` without an approval id.

### T4-E2E — Phase 6 continuous scenario (compiler DoD 19–20)
- **Status:** OPEN
- **depends_on:** all T4 cards above
- **Pressure:** 12 → Grok high effort
- **Acceptance:** [ ] the Phase 6 scenario passes in one run; [ ] no Bucket A guardrail weakened (diff review against `../01`).

### T4-GROUND — Dynamic tools grounded, RAG reuses the index, Odoo widgets (compiler DoD 11, 13, 14)
- **Status:** OPEN
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] dynamic tool targets resolve through `schema_client`; [ ] RAG reads the existing index, no second corpus; [ ] where a spec names an Odoo widget, the generated view uses it.

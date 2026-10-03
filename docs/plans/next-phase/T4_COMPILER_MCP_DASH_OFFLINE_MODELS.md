# Track 4 — compiler, MCP, dashboards, offline, models

Sources: compiler conceptual doc, compiler build spec (the build spec's phase order wins), MCP research, MCP build spec. MCP writes are forbidden by Track 5, which wins over any MCP server that exposes write tools.

Do not start ISPEC before Track 1 is done.

## Bucket B (new, default off until its confirm gate exists)

| Feature | Gate |
|---|---|
| Recompile | Confirm plus a diff. Never overwrite in place |
| Sync | Confirm plus a drift report. Drift blocks |
| Recompile with another provider | New versioned artifact, distinct from the previous |
| Write a Skill | Confirm plus blast radius |
| Trigger | Creation confirmed once. Each firing uses the underlying approval gate |

## Bucket C (deferred, do not build in this phase)

Full WYSIWYG spec editor. Multi-modal Sources beyond documents. Cross-project Skills.

## 6.1 Live progress

Four surfaces show stage-accurate progress: generation, Dashboard Studio, Expert, bulk operations. No generic spinner remains on those surfaces. Technical detail is opt-in. A tool-call limit asks the person to continue or stop. It does not continue silently.

## 6.2 MCP (read-only)

| Phase | Gate |
|---|---|
| 0 | Hands-on: search and aggregate return correct rows; YOLO versus standard permission difference is observed and written in the progress log. YOLO is never used in production |
| 1 | Detect native `mcp_server` when present and prefer it for reads. Smart field selection reduces payload, measured, default cap 15 fields. Aggregation on 19+ matches older majors. JSON-2 appears in request logs when the connection is 19+ |
| 5 | Fresh-instance dashboard session; BYOK question written down; competitive comparison written. This phase is research-complete, not a new product surface |

Stop-ship: any write-effect call through an MCP client. `call_model_method` style tools stay out of the Ingenium process.

## 6.3 AI Dashboard Studio

A dashboard is produced, persisted on the project, and cited. A protected model is declined or linked, not queried around. The guardrail is tested, not only designed.

## 6.4 Offline queue

IndexedDB queue plus ULID idempotency keys plus a server `IdempotencyStore` plus exponential backoff. A dropped ack does not double-apply. The queue survives reload and a second tab. A queued promote still requires a human confirm. Promote is never flushed automatically.

## 6.5 ISPEC, Recompile, Sync, browser agent

- ISPEC round-trip is lossless on complex fixtures.
- `ModuleSpec` remains the sole module IR. ISPEC serializes it; it does not replace it.
- Recompile never overwrites in place.
- Drift detection blocks.
- The browser-testing sub-agent, inside Stage F, catches at least one defect class that Python-only tests miss. Record the class. A claim without a caught defect does not pass.
- False-positive rate of the browser agent is written down.

Suggested paths (create under the web app, do not invent a second compiler): `spec/ispec/`, `spec/sync/`, `testing/browserAgent/`, `progress/`.

## 6.6 Wireframe

A real sketch becomes a spec. Ambiguity becomes a clarify step. Stage H human review always runs. Code inspection must show no bypass. Vision misreads are a risk, not a silent apply.

## 6.7 Three-tier models

Provider abstraction is swappable. `ClaudeProvider` (or the equivalent frontier adapter) is inactive by default. The gateway decision is ADR-02 / D8 and stays open: the card documents the choice and does not pick LiteLLM by default. The existing Gemini and Qwen paths keep working. No hard-coded model id, price, or context window outside the model registry (agent spec rule, applies here too).

## 6.8 Skills, Sources, Triggers

Critical gate: no code path treats "a trigger exists" as pre-approval of the write it will perform. Protected models are blocked. A Community trigger works without Enterprise. Audit attribution names the trigger, the person, and the plan hash.

## Compiler definition of done (1–20)

1. ISPEC round-trip is lossless.
2. ModuleSpec is the sole module IR.
3. Recompile never overwrites in place.
4. Drift blocks.
5. An alternate provider produces a distinct versioned artifact.
6. The browser agent runs in Stage F.
7. Its false-positive rate is documented.
8. Four surfaces have no generic spinners.
9. Technical detail is opt-in.
10. Tool-call limit exists on every long surface.
11. Odoo widgets are used, not generic stand-ins, where the spec names a widget.
12. Stage H always runs for wireframe output.
13. Dynamic tools are grounded.
14. RAG reuses the existing index rather than a second corpus.
15. Community triggers work.
16. Protected-model checks fire.
17. Trigger write confirmation cannot be skipped.
18. Audit attribution is present.
19. No Bucket A guardrail is weakened.
20. The Phase 6 continuous scenario passes.

## Risks that stop the track

Trigger auto-confirm bypass is stop-ship. ISPEC lossy round-trip and silent discard of a recompile are high. Flaky browser tours and vision misreads are medium and must be measured.

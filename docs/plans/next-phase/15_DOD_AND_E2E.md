# Definition of done and the end-to-end proof

A release candidate claims a number only when the progress log has evidence. Unclaimed numbers stay open.

## Master definition of done (verbatim intent, items 1–32)

1. Track 1: §3.2–§3.10 of the master spec complete, `scrub_uncued_*` retired, Maintenance and Service-cards goldens both pass with zero brief-specific code.
2. Track 1: D2 answered and encoded before PR-E ships. (D2 is answered. The card still encodes it.)
3. Track 2: D1 answered before PR-J1 starts; PR-J1–J4 complete; repo-wide grep for legacy RPC signatures returns nothing unexpected. (D1 is answered.)
4. Track 3: Phase 0–1 complete. Shopify passes Tiers I–III against real sandboxes.
5. Track 3: genericity proof passes. Tier 3b or 3c expresses Shopify identically to the hand-built connector, with zero changes above the connector interface.
6. Track 3: D3 resolved before customer-facing copy. (D3 is Ingenium Bridge.)
7. Track 4: live progress is stage-accurate on all four surfaces. No generic spinners remain.
8. Track 4: MCP detects and prefers native `mcp_server` when present.
9. Track 4: Dashboard Studio's protected-model guardrail works, not just exists in a design.
10. Track 4: the offline queue's idempotency store prevents a duplicate under a simulated dropped ack.
11. Track 4: ISPEC round-trip is lossless on complex fixtures. Recompile never overwrites in place. Drift detection blocks.
12. Track 4: the browser-testing sub-agent catches at least one defect class Python-only tests miss. Proven, not assumed.
13. Track 4: wireframe-to-app never bypasses full human review. Code inspection shows no bypass.
14. Track 4: the three-tier model provider abstraction is actually swappable. The production path is unaffected.
15. Track 4: the trigger-write confirmation gate passes. No path treats an automation as pre-approval.
16. Every track's audit logging captures real actions with attribution: Track 1's docket, Track 3's event log, Track 4's agent log, and they share the Track 5 chain.
17. No earlier guardrail (protected models, human-promote-only, sandbox-before-write) is weakened anywhere in the diff. Re-check at the end, not per track only.
18. D1–D5 are resolved. D4 and D5 were closed entering the master spec. D1–D3 are closed in this pack. D8, D10's numeric thresholds, and the pen-test remain the open tails; D10 and D11 and D12 are decided.
19. The cross-track scenario below passes as one continuous test.
20. The progress log reflects the true state of every track.
21. Track 5: `classify_rpc` is mapped onto Bucket A/B/C. Not a second system.
22. Track 5: structural dry-run-hash enforcement is on every write-capable tool in Tracks 1, 3, and 4.
23. Track 5: plan-fingerprint drift aborts apply. At least one operation per track.
24. Track 5: the never-allowed list is unbypassable at every autonomy level, including L4.
25. Track 5: one Worker Bot chassis runs representative tasks from Tracks 1, 3, and 4.
26. Track 5: the build-versus-adopt decision is recorded. It is D7: reimplement, oracle the package.
27. Track 5: zero write-effect calls go through an MCP client.
28. Track 5: a DESTRUCTIVE or BILLABLE production apply refuses without a successful snapshot immediately before.
29. Track 6: OAuth (Google and Microsoft) and email plus MFA work end to end with zero manual linking steps.
30. Track 6: Client Approver isolation fails a negative test, not only a review.
31. Track 6: auth and permission events are in the Track 5 hash chain. No second auth log.
32. Track 6: the consolidated dashboard shows live data from all five tracks at once.

## Compiler definition of done (1–20)

Copied in `T4_COMPILER_MCP_DASH_OFFLINE_MODELS.md`. A compiler release claims them there. They are part of master items 7–15, not a second exit.

## New items (this pack)

33. Odoo 20 is in the GA registry. The major-version gate installs and a representative read/write smoke passes on Community 20.
34. `ir.access` is the only security write on Odoo 20. A test fails if `ir.rule` is created there.
35. The version-difference table in T9 has a fake test and a live test per row that applies to 20.
36. Snapshots on Odoo 20 do not call the removed `db` service.
37. L4 cannot apply R3, R4, `module.*`, protected-elevate, or an op outside the tenant allow-list.
38. L4 demotes to L2 on a verify failure and rolls back.
39. UI foundation: Base UI families migrated, Sonner in place, `motion/react` respects reduced motion, axe covers every operate route the release touches.
40. The coverage matrix in `17` has no empty location for an ID family that this pack claims to include.

## End-to-end proof (one session)

1. Generate an app through Track 1, including a wireframe input from Track 4. Stage H runs.
2. Attach a skill and a scheduled trigger. The first firing asks a human. It does not run because the trigger exists.
3. Recompile with an alternate provider. The artifact is a new version. The old one is still there.
4. A Bridge contract to Shopify passes Tiers I–III.
5. Go offline mid-session. The queue flushes exactly once on reconnect.
6. The audit chain attributes steps 1–5 to the same actor and tenant.
7. Run again as a Worker Bot at L2: every write pauses. Then at L3 on staging: REVERSIBLE may proceed, DESTRUCTIVE and BILLABLE pause.
8. A consultant signs in with Google and approves from the dashboard. A Client Approver sees those cards for their client and receives 404 for a second client.

Gate: all eight in one session. No guardrail bypass. Bucket A re-audit clean. Step 7 is one chassis. Step 8 is a real control, not a hidden button.

## What this pack does not claim

Pen-test (GATE-P7-03), 30-day pilots (GATE-P8), and L4 eligibility evidence (GATE-L4-08) are not done because this pack is documentation. Cards must not check those boxes in advance.

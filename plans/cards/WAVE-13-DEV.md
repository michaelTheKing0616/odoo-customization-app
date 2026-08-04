# Wave 13 — DEV: first-class developer code path (user-directed 2026-08-03)

Purpose: developers must always be able to write Python directly — live where the instance
allows it, via the module path everywhere else, and as ad-hoc scripts — WITHOUT weakening the
no-code path's safety posture. This wave completes (does not contradict) MEMORY 2026-07-27
"Python path = Option A; advanced actions with confirm": Option A remains the default;
direct code is an explicit, gated, audited opt-in.

Cross-cutting rules for all three cards:
- Everything routes through TRUST-2's SafetyGate with risk class `code` (snapshot + advanced
  confirm phrase + audit including the FULL code content in the journal record).
- Observer-mode connections refuse all of it (TRUST-1). Kill switch + anomaly guard apply.
- Developer surfaces are gated by a per-workspace `developer` role grant (admin+ grants it;
  MON role matrix extended) AND entitlement key `dev_tools` (Business+; internal bypasses).
- Capability is PROBED per connection, never assumed by hosting tier ("where allowed" is an
  instance fact, not a marketing table).
- Runs after Wave 12 TRUST (depends on SafetyGate + write modes). Routing: DEV-1, DEV-3 →
  Grok 4.5; DEV-2 → Composer. Checker Grok, new session.

---

## DEV-1 — Code Studio: live code server actions + code automations (Grok 4.5)

TASK: Let developers author `state=code` server actions and code-type automation actions
directly on instances that verifiably allow them, with an editor, sample-record test runs,
and the full confirm/snapshot posture.

CHECKLIST:
- [x] Capability probe + matrix row `code_server_actions`: on connect (or on first Code
      Studio open), verify per instance that `ir.actions.server` accepts `state='code'` via
      RPC — probe by fields_get selection inspection PLUS a create→run-on-nothing→unlink
      round-trip of a trivial no-op action (`x = 1`) with cleanup guaranteed (try/finally);
      record result + error detail; Online instances get probed like everyone else (result,
      not assumption). Failure → honest Callout with the module-path alternative
      (COPY_GUIDE three-options template).
- [x] Editor surface: Code Studio page (nav Build group, `developer` role + `dev_tools`
      gated) — Monaco (or CodeMirror — pick the lighter one that supports Python
      highlighting + diagnostics hooks; document choice) with: safe_eval context reference
      panel (records/env/model/log/UserError etc. per Odoo's documented server-action
      context, version-tagged), snippet templates (set field, create activity, post message,
      guard clause patterns), and static pre-checks before save (syntax compile check
      server-side; warn on imports — safe_eval forbids them anyway; warn on `unlink`/`sudo`
      patterns with an extra consequences line in the confirm).
- [x] Test run before bind: execute the action against ONE user-chosen record (or none for
      context-free code) with captured result/exception + a diff-style report of what the
      record's fields looked like before/after (read before, read after) — clearly labeled
      "this ran for real on that record" (honest; recommend picking a test record; on
      dirty-gate instances this is exercised in tests).
- [x] Bind targets: standalone server action (Technical-style), contextual action button on
      a model, or automation action (base_automation code step) — all with the Odoo-style
      warning + advanced confirm + snapshot; created artifacts fully covered by existing
      snapshot/rollback + journal.
- [x] Odoo Expert integration: "Explain this code" + "Draft code for me" buttons route to
      the Expert with the safe_eval context — drafts land in the editor, NEVER auto-bound
      (review + confirm always human).
- [x] Tests: probe round-trip incl. cleanup-on-failure, gating matrix (role × entitlement ×
      write-mode × probe result), test-run before/after capture, bind paths live on docker
      19, refusal shapes; adversarial: non-developer role cannot reach any Code Studio
      endpoint.

DONE MEANS: on docker 19, a developer writes a code action in the editor, test-runs it on one
record with a before/after report, binds it as a model button through confirm+snapshot, and
the journal shows the full code; a failed probe renders the honest alternative instead.

DO NOT: bypass safe_eval or attempt to widen Odoo's sandbox; assume code actions by hosting
tier; auto-apply Expert-drafted code.

GATE: `uv run pytest tests/test_code_studio*.py -q` + RPC smoke 19 + e2e editor flow.

---

## DEV-2 — Module code authoring: Option A with a real editor

TASK: Turn the module escape hatch into a workable developer experience: write/edit Python
(compute methods, constrains, controllers, business logic) inside a ModuleSpec, ride the
existing export → sandbox → promote pipeline.

CHECKLIST:
- [x] Make AI-7's `custom_code_blocks` read-WRITE for developer-role users: the ModuleSpec
      editor "Custom code" tab becomes an editor (same component as DEV-1) supporting
      add/edit/delete of Python files (models/*.py, controllers) and raw XML blocks, with
      file placement controls; non-developer users keep the read-only view.
- [x] Authoring aids: model class skeleton generator from the spec (fields typed from
      ModuleSpec — compute/constrains stubs wired to real field names), manifest deps
      surfaced, lint pass (pyflakes-level: syntax + undefined names) on save with inline
      diagnostics; XML well-formedness check.
- [x] Pipeline unchanged and enforced: code blocks NEVER apply via the live path (existing
      AI-7 skip behavior verified intact) — banner in the tab: "Code ships as a module:
      export → sandbox → promote"; one-click "Export & sandbox-test" from the tab, surfacing
      sandbox install logs (incl. tracebacks) inline for the edit-test loop.
- [x] Round-trip integrity: edited blocks survive spec save/export/import byte-identically
      (extends AI-7's tests to the write path).
- [x] Promote posture unchanged: sandbox validation token + confirm still required (existing
      promote gates); remote no-filesystem targets still refuse Python zips honestly
      (existing behavior — verify with a named test, don't rebuild).
- [x] Tests: editor write path round-trip, lint diagnostics, sandbox-loop e2e (author a
      compute method → export → sandbox gate passes → method works on installed model),
      role gating.

DONE MEANS: a developer authors a compute method in the app, sandbox-tests it in one click,
and promotes through the existing gates — with zero change to the live-path safety promise.

DO NOT: allow code blocks into the live apply path; hand-roll a Python parser beyond
lint-level checks; weaken promote's sandbox requirement.

GATE: `uv run pytest tests/test_module_import.py tests/test_custom_code_authoring.py -q` +
sandbox gate + e2e.

---

## DEV-3 — Script Runner: ad-hoc Python against a connection (Grok 4.5)

TASK: The "ten lines of Python right now" lane: run one-off scripts against a connection
through the typed RPC client, in an isolated subprocess on OUR side — the developer power
tool that never touches the customer server's filesystem or shell.

CHECKLIST:
- [x] Execution sandbox: scripts run in a separate OS subprocess with resource limits
      (CPU/time — default 120s, memory cap, no subprocess spawning), a minimal allowlisted
      import set (stdlib subset + provided client), NO general network and NO filesystem
      writes except an output buffer — implemented via a restricted bootstrap + OS-level
      limits (resource/rlimit; document what is and isn't guaranteed vs a container; if the
      docker sandbox infra is trivially reusable for stronger isolation, prefer it and
      document the choice).
- [x] Script context: injected `odoo` handle = the typed odoo-client for THIS connection
      (same credentials/permissions as everything else — the structural safety bound holds:
      scripts can't exceed the connection user), plus `log()`, `progress(n, total)`;
      stdout/stderr captured and streamed to the UI console.
- [x] Safety posture: SafetyGate risk class `code`; advanced confirm before every run
      (script content hashed + stored in the journal); observer mode refuses; anomaly guard
      counts script writes; kill/abort terminates the subprocess (TRUST-tested pattern);
      optional but default-ON "count writes" wrapper reporting created/written/unlinked
      record counts per model in the run summary (wrapper around the client's mutating
      methods).
- [x] UX: Script Runner page (Operate group; `developer` role + `dev_tools` gated) — editor,
      connection picker (write-mode-aware), run/abort, live console, run history with
      script content + output + write counts (journal-linked); saved-scripts library per
      workspace with share-within-workspace.
- [x] Templates: 5 authored starter scripts (safe patterns: batched read+report, guarded
      mass write with dry-run flag convention, data export to CSV output, orphan checker,
      activity scheduler) — each demonstrating the `log`/`progress`/write-count idioms.
- [x] Tests: sandbox limits (timeout kill, memory cap, import allowlist, no-network, no-fs
      write), abort mid-run, write-count accuracy (fake client), role/entitlement/
      write-mode gating matrix, journal record completeness; live smoke on docker 19
      (batched write script on x_ records).

DONE MEANS: a developer runs a saved script against docker 19 from the UI with live console
output, write counts, and abort working; the sandbox limits suite proves timeout/memory/
import/network/filesystem containment; every run is journaled with full content.

DO NOT: execute scripts in the API process; grant filesystem or general network access;
allow script execution on observer connections; exceed the connection user's Odoo
permissions (structurally impossible via the client — keep it that way; no raw endpoint
escape hatch).

GATE: `uv run pytest tests/test_script_runner*.py -q` + RPC smoke 19 + e2e console flow.
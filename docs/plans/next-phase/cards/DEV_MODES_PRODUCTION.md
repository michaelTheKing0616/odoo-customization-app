# Cards — Code Studio, Script Runner, Power Ops (walk-away)

Queued 2026-10-04. Tope: these three must be safe to hand to a customer without the founder in the loop. They already exist. These cards close the gaps. They do not start while T6-06 is claimed.

**Walk-away means:** a customer with the developer role and the `dev_tools` entitlement can open the screen, see what it will do, confirm, and recover if it fails. The founder is not required.

**Walk-away does not mean:** unattended apply, a hidden bypass of the hard stop, or a live SQL console. Promote of a module stays a person. L4 stays off. Raw SQL, `rpc.write`, payment secrets, posted accounting entries, lock dates, and a group-less access rule stay out of the plan. The same work remains available in Odoo, and ordinary Odoo methods remain available in Script Runner and Power Ops except the never-allowed list (user/company/XML-id/config-parameter unlink, API keys, database secrets).

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; no customer database; `:8001` does not reload; never loosen a test; no live LLM in a PR test; do not edit `agent_runtime` unless the card names it; do not enable L4; do not auto-promote a module.

**Already built (do not rebuild the behavior):** `apps/api/app/code_studio_service.py`, `code_studio_gating.py`, `routers/code_studio.py`; `apps/api/app/script_runner/`; `apps/api/app/power_ops_recipes.py`, `routers/power_ops.py`; web pages `connections/[id]/code-studio`, `script-runner`, `power-ops`. UI-S-18, UI-S-35, and UI-S-31 remain the screen specs. These cards still ship the premium surface. A later restyle is not an excuse to leave a plain form.

**UI bar (Tope, 2026-10-04):** excellent, current, and tasteful. Load the Prime skills for taste, motion, copy, and accessibility before editing. Use the studio tokens, Base UI, and Sonner. Operate density stays calm. Motion is interruptible, transform/opacity, under 300ms, and reduced-motion safe. Every screen has empty, loading, error, and success states. The confirm step is part of the design, not a browser `window.confirm`. Code Studio's editor highlights Python and puts the diagnostic next to the line. A plain textarea does not pass. Do not invent a second visual language.

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_code_studio_gating.py tests/test_code_studio_live.py \
  tests/test_script_runner_gating.py tests/test_script_runner_sandbox.py \
  tests/test_power_ops.py tests/test_power_ops_forbidden.py
```

**Audit events:** `change` for a live server action or a script run; `module` for an Option A zip; `apply` only after the confirm phrase and a snapshot id.

---

### DEV-CS — Code Studio a customer can use alone
- **Status:** DONE
- **depends_on:** none. Do not start while T6-06 is claimed.
- **Pressure:** C3 U2 F3 K3 V2 I2 +0 = 15 → frontier + reviewer
- **Read first:** `apps/api/app/code_studio_service.py`, `apps/api/app/code_studio_gating.py`, `apps/api/app/routers/code_studio.py`, `apps/web/src/app/connections/[id]/code-studio/page.tsx`.
- **Steps:**
  1. Keep the two paths distinct on the screen: restricted server-action code, and an Option A module that sandboxes and waits for a person to promote.
  2. A live bind still requires the instance probe, the developer role, `dev_tools`, the confirm phrase, and a snapshot. Observer mode and a missing entitlement refuse the write.
  3. Imports, `sudo`, and `unlink` stay blocked on the server-action path. The error names the rule.
  4. A failed test-run does not bind. The screen shows the failure and the snapshot id.
- **Acceptance:** [x] a customer can bind a server action only after probe + confirm + snapshot (pytest 25 passed, including snapshot-before-create, missing phrase, and failed probe); [x] Option A produces a zip and does not install it (`test_option_a_zip_is_not_installed`, `test_export_option_a_zip_has_no_install_side_effect`); [x] the screen states both limits in the product UI, not only in a doc (vitest 5 passed; both limit cards visible in the browser).
- **Negative:** an import, a missing confirm phrase, an observer connection, and a failed probe each refuse the bind. No `state=code` row is written in those cases.
- **Do not:** execute the server action inside the API process. A plain textarea does not pass the UI bar.

### DEV-SR — Script Runner a customer can use alone
- **Status:** OPEN. Stopped 2026-10-04 after two repairs. Do not start a third until the sandbox approach changes. See `ERRORS.md` 2026-10-04.
- **depends_on:** DEV-CS
- **Pressure:** C3 U2 F3 K3 V2 I3 +0 = 16 → frontier + reviewer
- **Read first:** `apps/api/app/script_runner/service.py`, `apps/api/app/script_runner/executor.py`, `apps/api/app/routers/script_runner.py`, `apps/web/src/app/connections/[id]/script-runner/page.tsx`.
- **Steps:**
  1. A run stays in a subprocess with the import allowlist. It does not gain the filesystem or the network.
  2. The journal records the script hash, the connection, the write count, and the outcome. A crash leaves a failed row, not a silent success.
  3. The never-allowed RPC list is enforced on this path. The confirm phrase is required before a write.
  4. The screen shows the last run, the failure, and how to restore from the snapshot when a snapshot was taken.
- **Acceptance:** [ ] a write script without the confirm phrase does not call Odoo; [ ] a forbidden RPC does not leave the process; [ ] a crashed run is visible as failed.
- **Negative:** `res.users` unlink and a protected database parameter are refused. A second run of the same script is a new journal row, not an overwrite of the first.

### DEV-PO — Power Ops a customer can use alone
- **Status:** OPEN
- **depends_on:** DEV-SR
- **Pressure:** C3 U2 F3 K3 V2 I3 +0 = 16 → frontier + reviewer
- **Read first:** `apps/api/app/power_ops_recipes.py`, `apps/api/app/routers/power_ops.py`, `apps/web/src/app/connections/[id]/power-ops/page.tsx`.
- **Steps:**
  1. Every destructive recipe dry-runs first. The live run requires the confirm phrase and a snapshot id.
  2. A forbidden method never reaches Odoo. The recipe grid says which recipes write and which only read.
  3. A partial recipe stops, records how far it got, and does not report the whole recipe as done.
  4. The screen offers the snapshot restore where Odoo allows it, and says so when it does not.
- **Acceptance:** [ ] dry-run then confirm then snapshot, in that order, for a destructive recipe; [ ] a stopped recipe is not marked complete; [ ] the grid names the write.
- **Negative:** `approved=true` does not skip the forbidden-method check. A recipe that would unlink `res.users` does not call `execute_kw`.

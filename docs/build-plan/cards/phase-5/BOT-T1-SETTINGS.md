# BOT-T1-SETTINGS — PAUSED

Paused 2026-10-26 by the priority change (BOT-FITGAP first). Nothing implemented; no repo code.

Findings to resume from:
- Catalogue has `s:<field>` settings rows (562 R2 reversible, 142 R7); the risk classifier puts
  `s:group_*` toggles at R8 / L3.
- Planned approach: apply through WriteGate with an adapter rpc (write -> create
  res.config.settings transient + `execute`); idempotency = audit claim + state check; undo =
  a gate run restoring before-values; `module_*` fields L3 with a snapshot, uninstall refused;
  readback checks the admin user count (no lockout). No raw-write exemption needed.
- Sandbox DBs on PG 54349: `ingenium_nf2_set_17`, `ingenium_nf2_set_20` (sale_management, stock,
  purchase, no demo). Init needs `-e HOST=host.docker.internal -e PORT=54349 -e USER=ingenium
  -e PASSWORD=ingenium`.

## Result (2026-10-26, resumed after BOT-FITGAP)
Status: built, awaiting independent review. No git writes.

Files: `apps/api/app/bots/settings.py` (SettingsBot: plan/apply/undo/admins),
`apps/api/tests/test_nf_bot_settings.py` (12 tests, real audit DB via kill_audit fixtures, fake Odoo).

How it works
- plan: each field must be on the live Settings form (fields_get), writable, typed
  (boolean/integer/float/char/selection/many2one; selection value must be a live key), and a
  catalogue `s:` row allowed by the classifier for this version. Anything else refused
  (fail closed; classifier unavailable = refused). `module_*` False (uninstall) always refused;
  `module_*` True = L3 + snapshot required. Before-values from default_get; unchanged fields dropped.
- apply: only `WriteGate.call` (create wizard, then `execute`), each its own claim/grant/key
  (`<key>:create`, `<key>:execute`). Already-at-target = replayed done, no write. Changed since
  preview = refused. Readback: values via default_get + active admin count (base.group_system);
  mismatch or fewer admins = kill switch on, status mismatch/lockout.
- undo: new plan to the before-values, applied the same way; refused for app installs,
  replayed runs, or if settings moved since apply.
- No raw RPC writes: settings.py passes `test_no_raw_rpc_writes_in_bots` and its own AST pin.

Tests: settings 12 passed; suites fitgap/kill_audit/lockout_sim/risk*/sinkhole/v20_access/walker
+settings forward 2475 passed/6 skipped, reverse file order same, test-level reverse
(settings+kill_audit+walker) 148 passed. Ruff clean.

Gaps (known, not fixed here)
- Live Odoo 17/20 run on `ingenium_nf2_set_17/20` not done; fake Odoo only.
- Gate dedupes by plan hash: re-applying an identical change later in the same DB (e.g. after
  an undo) is not done (needs-human/mismatch, kill switch may trip). Fails closed, but noisy.
- Crash between create and execute: re-run with the same key returns needs-human (gate holds
  the key); a leftover transient wizard is harmless (Odoo vacuums it).
- `execute` side effects (installs, cron/mail settings) are not held by Sinkhole; no automatic
  undo after a lockout/mismatch trip, a person restores from the before-values in the result.
- Lockout check is admin count only (not the walker's full lockout simulation).
- many2many/one2many settings unsupported (refused).

## Review follow-ups

Low findings from the independent review (APPROVE round 1), not blocking:

1. `group_*` settings imply groups onto every internal user, including the bot. Add a post-apply check that the bot's own groups did not grow.
2. `external_email_server_default` is R2/L1; it should be R8 or L2.
3. The raw-write detector in `tests/test_nf_bot_kill_audit.py` (~:599) only covers write/create/unlink; add execute, set_values, button_immediate_install.
4. A save failing halfway leaves values partly applied with no kill switch (safe but manual). Multi-company not tested. Live Odoo 17/20 check not yet run: do it in BOT-SPINE-WIRE or the next live round.

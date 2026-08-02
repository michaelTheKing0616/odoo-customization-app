# Skill: Advanced actions, confirmation, and rollback

## Product rules
1. **Safe by default** — no-code path: update field, activity, standard view/model edits.
2. **Advanced with eyes open** — code, webhook, equation compute, delete field/model, promote
   Python module to prod: show Odoo-style warning (risk summary + what may be irreversible)
   and require explicit confirm (`confirm_advanced=true` and optionally typed phrase).
3. **Python = Option A** — never write live `ir.actions.server` `state=code` from the default
   builder without going through: generate module → sandbox → promote.
4. **Snapshot first** — before risky mutate, store a restore payload in app DB keyed by
   connection + resource. Rollback restores that payload via RPC when possible.
5. **Promote** — `POST /connections/{id}/modules/promote` needs sandbox validation (or
   `run_sandbox=true`) + confirm phrase. Local Docker → filesystem; remote → `install_mode=data`.

## Reversibility honesty
| Action | Rollback |
|---|---|
| View arch write | Yes — restore previous arch |
| Automation / server action create | Yes — unlink or restore vals |
| Field create | Partial — uninstall/remove field if unused; data may remain |
| Field delete | Often **no** — warn; snapshot definition only |
| Model delete | Often **no** — warn |
| Module install with code | Yes — uninstall module / restore prior module zip version |

## API contract
```
POST ...? or body: { "confirm_advanced": true, "confirm_phrase": "I understand the risks" }
```
Without confirm → `403` with `requires_confirmation` + human-readable warning.

## UI contract
- Red/amber Odoo-style dialog: title, bullet risks, checkbox or typed confirm, Cancel / Proceed.
- After success: show **Undo** when a snapshot id was returned.

# Copy glossary (internal → user-facing)

Use these words in anything a person reads: screens, menus, buttons, toasts, empty/error states, tooltips, and API messages returned to the UI. Keep internal names in code identifiers, keys, routes, and test ids.

| Internal term | User-facing words |
|---|---|
| Option A / Option A lane | custom code / custom-code path (build, test on a test copy, then publish) |
| Promote (action) | Publish / Publish to Odoo / publishing |
| Prefer (verb in copy) | Try / Use (e.g. "Try a test copy first") |
| Prefer pack / Prefer inherit | Field pack / extension view |
| residual / Custom residual | custom code / custom app |
| lane | path |
| grain (`full_app` / `field_pack` / `feature_slice`) | Full app / Field pack / Feature under an existing app |
| IR / ModuleSpec | app plan / your app's plan |
| Cert / Certification / Cert ≥ Production | quality checks / quality checks pass for production |
| Autopilot completeness / Completeness ≠ Cert ≠ Autopilot | draft completeness; a complete draft is not the same as certified, and neither means Autopilot-ready |
| stock-first / stock-only | built-in apps first / built-in apps only |
| host model / stock host | existing form / built-in form |
| inherit (UI sense) | extension view (keep technical `strategy=inherit` in APIs) |
| sandbox | test copy |
| Config Packet / Plan packet | config summary / plan summary |
| grounding | what we know about your database / matched from your documents |
| Stage H | layout preview |
| changeset | change set (or omit; say "proposed changes") |
| L4 / T8-… / rubric / golden / packet (internal) | never show; use plain outcome language |
| x_* | only when the user is looking at technical names |

## Style

- Sentence case. Plain human copy. No `(s)` plurals. No ALL CAPS shouting.
- Odoo terms: scheduled actions, automation rules, access rights.
- Errors say what happened and what to do next.

# BOT-OWNED-CODE-CHANGE
No card existed; derived from RESOLUTION.md, MEMORY.md and t463u plus the dispatch brief.
Structured edits (replace_file, add_file, delete_file, replace_symbol, replace_xmlid) against an
owned module tree produce a ChangeSet: unified diff, inverse diff, base/after sha256, pre/post
code_audit counts, stable id and L3 approval facts. Pure: never writes or executes.
Fails closed: foreign module, tree/module mismatch, nested module, path escape, symlink/hostile zip,
syntax error, ambiguous target, no-op, bounds, any new high/medium finding.
apply_change_set: base->after, already-after = no-op, drift = stale-base; reverse restores bytes.
Request reason is metadata only. T3 switches unchanged.
Impl: apps/api/app/bots/owned_change.py; tests: apps/api/tests/test_nf_bot_owned_change.py (23).
## Gaps
- No live Odoo install/upgrade of the changed module (static audit only).
- replace_xmlid locates by regex text span (record/template/menuitem/act_window/report); unusual formatting may miss.
- replace_symbol is top-level or Class.method only; whole-file single-hunk diffs (big files give big diffs).
- New-finding comparison keys on (code,file,message), ignoring line; a moved identical finding is not 'new'.
- Approval: approval_plan() emits L3 facts only; not wired into ApprovalStore/apply (BOT-SPINE-WIRE).
- Ownership trusts caller's owned_names registry.

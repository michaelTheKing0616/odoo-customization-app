# Skill: Odoo 19 RPC Gate

## When to use
Any task that creates or changes Odoo RPC helpers, metadata writes (`ir.model`,
`ir.model.fields`, `ir.ui.view`, `base.automation`, access rules), or generated modules.

## Why
Models confidently invent Odoo API shapes. A unit mock green ≠ works on Community 19.
This gate is the mechanical fail (RULES.md Rule 4) for Odoo-facing work.

## Done means (all required)
1. Local Docker stack is up: `odoo:19` + Postgres, reachable on the expected port.
2. Scripted proof ran against that instance (not mocked): connect → authenticate → exercise
   the new/changed call → assert response shape.
3. Output captured (exit code 0 + short log path or inline result) for the judge/checker.
4. For destructive ops: snapshot/backup step ran first, or the call was limited to a
   throwaway DB named for testing.

## Card fragment (paste into worker cards)
```
DONE MEANS: pytest/script against local odoo:19 returns exit 0 for the new RPC path;
  paste the command and last 20 lines of output in RETURN.
DO NOT: mark done based on mocks alone; do not write to any non-sandbox Odoo URL.
```

## Checker notes
- Cheap tier can grade "did the smoke script exit 0?"
- High tier checker for: security of generated automations, correctness of view XML vs
  golden examples, whether a field delete is safely gated.

## Known failure modes
- Using Odoo 17/18 docs mental model on 19 without checking changelog differences.
- Treating `base.automation` Community availability as identical action types across versions.
- Installing a generated module on the shared dev DB without the ephemeral sandbox path.

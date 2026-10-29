# BOT-REQ2MOD: requirement to module spec (T3 input)

Source: no prior card existed. This card is derived from Tope's t463u ("bots handle any task,
including T3"), the TAX-TIERS T3 registry, and module_generator.ModuleSpec as the authoring input.
Code: `apps/api/app/bots/req2mod.py`; tests: `apps/api/tests/test_nf_bot_req2mod.py`.

Takes a structured, generic requirement: record types with fields, states and chatter;
extra fields on stock models; roles with r/w/c/d access and own-records-only; and rules
(when, if, then). Returns a `ModuleSpec` with models, fields, views, actions, menus, groups,
access, record rules, automations and Odoo tests, plus a trace and assumptions.

Acceptance criteria, each tested:
1. Every requirement item traces to at least one spec element.
2. The spec renders to a module zip for Odoo 17-20, ISPEC round-trips, generated Python parses,
   and list views and manifest version follow the major.
3. Security: every new model has access for a named role, and access letters are validated.
   Own-only becomes a record rule; it is refused where ir.rule is absent (20). Groups drop
   category_id on 19+.
4. Automation code comes from a closed vocabulary (set a field to a literal, post a note).
   Requirement text is only ever a literal.
5. Bad input fails closed with a reason, and no partial spec is returned.
6. It never switches T3 on: `runnable` follows `tiers.tier_ready(T3)`.
7. Read-only: no Odoo client, RPC or writes.
8. Version-aware: relations, extensions and depends come from versioncaps for that version.
9. The generated tests create each new record type and assert every role's access.

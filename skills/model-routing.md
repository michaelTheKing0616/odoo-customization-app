# Skill: Model Routing by Task Complexity

## When to use
Before starting any task — decide which model handles it before writing the prompt/brief.

## Default routing table

| Task type                                                  | Model                          |
|--------------------------------------------------------------|---------------------------------|
| Architecture decisions, hard debugging, deep review           | Opus / high-reasoning tier     |
| Odoo ORM/RPC design, module generator correctness, security   | Opus / high-reasoning tier     |
| Sustained multi-file coding sessions, routine feature work    | Composer / agentic coding tier |
| Same as above, latency-sensitive                              | Composer Fast (costlier)       |
| Boilerplate, lint, simple refactors, doc updates              | Sonnet / mid tier              |
| Test scaffolding, repetitive fan-out work                     | Sonnet / mid tier              |
| Mechanical grading (tests pass? schema match? zip structure?) | Haiku / cheap tier             |
| Judgment-heavy verification (security, destructive metadata)  | Opus, separate session         |
| Vision-verify UI (view designer, field builder)               | Vision-capable checker + screenshot |

## Project-specific routing notes
- **View designer XML** — mid/high maker + independent checker with golden XML examples in the card; cheap models hallucinate Odoo view directives.
- **RPC wrapper** — agentic coding tier to implement; gate = live call against Docker Odoo 19 (not unit mocks alone).
- **Module generator Jinja templates** — mid tier for templates; high tier for `_inherit` / security CSV correctness review.
- **Sandbox Docker pipeline** — agentic coding; gate = container install + module load success/fail.

## Why Composer gets its own tier
Composer is Cursor-trained for sustained agentic coding (files, terminal, iterate on errors).
Strong default for the middle ~80% of the barbell (PIPELINE.md). It has no public API —
checkers for Composer-made artifacts must use a new Cursor chat (RULES.md Rule 6), not a
scripted API call. Scheduled automation needs Cursor CLI.

## Rule of thumb
Default down a tier. Escalate only if the cheaper model's output fails the checker twice in
a row. Log which tier handled each task type; promote task types that keep failing.

## Known failure modes
- Expensive model on boilerplate (field form labels, CSS tweaks).
- Cheap model + cheap checker on destructive Odoo metadata or security-sensitive automations.
- Treating agentic coding strength as design/judgment strength — architecture stays on the high tier.

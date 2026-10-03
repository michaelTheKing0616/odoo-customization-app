# Skill package format and router

**Status:** accepted (engineering spec, 2026-10-03). This records the format. It does not claim the router is built.

**Context:** The bot engine loads skills as packaged procedures that a router selects from labeled phrasings. A skill that ships executable code or widens a grant would become a second execution and privilege path beside the current grant. T8 already states the package and router bars; this ADR locks them so later skill cards cannot invent a wider contract.

**Options considered:**
- Skills may contain executable code and may widen a grant. A loaded skill could run code and raise the effective permission above the current grant.
- The T8 skill rules. No executable code in a skill. A skill can only narrow a grant, never widen it. At most 3 skills loaded by default. `SKILL.md` is at most 2500 tokens. Router: recall@3 at least 0.95, precision@3 at least 0.6, on at least 300 labeled phrasings. CI: at least 5 evals per skill, at least 12 for Tier-1. `knowledge_freshness_days` example 180.

**Decision:** Use the T8 skill rules. No executable code in a skill. A skill can only narrow a grant, never widen it. At most 3 skills loaded by default. `SKILL.md` is at most 2500 tokens. Router: recall@3 at least 0.95, precision@3 at least 0.6, on at least 300 labeled phrasings. CI: at least 5 evals per skill, at least 12 for Tier-1. `knowledge_freshness_days` example 180.

**Consequences:** A skill that runs code becomes harder: there is no executable code in a skill. A skill that widens a grant becomes harder: a skill can only narrow a grant, never widen it. Default load stays at most 3 skills, and `SKILL.md` stays at most 2500 tokens. The router is not claimed built; when it ships it must meet recall@3 at least 0.95 and precision@3 at least 0.6 on at least 300 labeled phrasings, with at least 5 CI evals per skill and at least 12 for Tier-1. `knowledge_freshness_days` example 180.

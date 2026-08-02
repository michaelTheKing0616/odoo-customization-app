# Skill: Verifier / Checker Sub-Agent

## When to use
Any time a maker session (any model — Opus 4.8, Composer 2.5, Sonnet 5) produces a
non-trivial artifact — code, a generated report, a UI, a simulation result — and you're
tempted to just ask the same session "does this look right?"

## Why
A model checking its own output sees its own reasoning trail and tends to prefer
conclusions consistent with what it already wrote. A separate context sees only the
artifact and the rubric, with no reasoning trail to be swayed by.

## How (Cursor-specific)
1. Maker finishes work in its worktree, states the goal/rubric explicitly if not already
   written down.
2. Open a **new, unrelated Cursor chat** for the checker (required if the maker was
   Composer 2.5 — no public API means a scripted call isn't an option). For API-reachable
   models (Opus 4.8, Sonnet 5, GPT-5.5 Codex), a small script hitting the provider API
   directly also works. Either way: do not continue the maker's conversation.
3. Give the verifier only: the goal/rubric, and the artifact (diff, file contents, test
   output, or screenshot). Do not give it the maker's explanation of *why* it did things.
4. Verifier returns a pass/fail plus, on fail, a structured description of the gap — not a
   vague "this seems off."
5. On fail, hand the structured gap description back to the maker for the next iteration.
   Cap iterations (see RULES.md Rule 4).

## Known failure modes
- Accidentally pasting the maker's own reasoning into the verifier prompt (defeats the
  purpose — verifier now has "skin in the maker's game").
- Using a lighter/cheaper model as verifier for tasks where domain judgment actually matters
  (fine for lint/test-pass checks, risky for e.g. judging whether a rating engine change is
  statistically sound).

## Cheap alternative
Haiku 4.5 (or equivalent low-cost model) is fine as verifier for mechanical checks (tests
pass, lint clean, schema matches). Reserve a stronger model as verifier when the judgment
itself is hard (e.g. "is this simulation's variance realistic").

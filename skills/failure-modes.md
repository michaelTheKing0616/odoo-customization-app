# Skill: The Five Failure Modes

## When to use
Before scaling any loop or team beyond a single manual run — and as a diagnostic checklist
when a running system starts producing weak output for no obvious reason.

## The five modes

**The echo chamber.** No checker, or a checker too polite to actually fail anything.
Everything passes; days later the batch turns out to be mediocre across the board.
→ Fix: a real, separate checker with strict pass/fail rules (RULES.md Rule 6), not a
second opinion from the same maker.

**The early victory lap.** A worker or the loop itself declares "done" on a half-finished
job and the orchestrator takes the claim at face value.
→ Fix: claims don't count, deliverables do. The judge reads a diff, test result, or file
list — never a sentence asserting success (RULES.md Rule 3).

**The token fire.** Every worker re-reads the whole project on every pass; a 10-iteration
loop becomes 10 increasingly expensive prompts instead of 10 equal-cost ones.
→ Fix: workers get card-scoped context only (`team-brief-and-cards.md`); only the
orchestrator holds the full map.

**The same-file collision.** Two workers touch the same file; one silently overwrites the
other's change.
→ Fix: own folder or branch per worker, always, no exceptions (RULES.md Rule 5).

**The team that shouldn't exist.** The overhead of briefs, handoffs, and checks costs more
than the task is worth — usually a one-off job that would've been faster as a single good
prompt.
→ Fix: check RULES.md Rule 14 before building anything. A loop only pays off when the task
repeats at least weekly, something can mechanically reject bad output, the model can finish
it end-to-end, and "done" is objective.

## Diagnostic use
If a running system's accept rate (RULES.md Rule 13 — cost per accepted result) drops below
~50%, walk this list before assuming the model got worse. Most degradations trace back to
one of these five, not to the underlying model.

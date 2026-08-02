# Skill: The Brief and The Card

## When to use
Any time you're delegating non-trivial work — to an orchestrator model, to a subagent, or
to yourself-as-orchestrator manually splitting a task.

## Why
Agentic setups don't usually fail from a weak model. They fail from a vague brief — the gap
between what you wrote and what you actually meant is where most bad batches come from.

## The brief (you → orchestrator)
```
CONTEXT: what this is, who it's for, why it matters.
REQUEST: the outcome, not the steps.
OUTPUT FORMAT: exactly what lands on disk — files, structure, naming.
CONSTRAINTS: what it must not break on its own (stack, tone, budget, off-limit files).
```
Add the checkpoint clause so autonomy stays safe without turning chatty:
```
Run this end-to-end. Use as many subagents/sessions as the job requires.
Pause for me only when it genuinely matters: spending money, sending
anything external, or a judgment call only I can make. Otherwise don't
stop. Show me the finished work when it's done.
```
On unfamiliar territory, run an interview pass before writing the brief:
```
Interview me, one question at a time, about anything ambiguous in this
task. Prioritize questions where my answer would change the plan. Stop
when you could write the brief yourself.
```

## The card (orchestrator → worker)
```
TASK: one sentence, one outcome.
INPUT: exactly which files/data the worker gets. Nothing else.
DONE MEANS: an objective, checkable line.
DO NOT: files not to touch, decisions not to make alone.
RETURN: a summary under 10 lines + the deliverable itself.
DEVIATIONS: if an edge case forces a change of plan, take the
  conservative option, log it under "deviations" in the return, and
  keep going. Never silently improvise.
```
Workers see only their own card, never the full plan. This keeps context narrow (cheaper,
less prone to drift) and prevents two workers from making conflicting assumptions about
scope they were never given.

## Known failure modes
- Skipping the interview pass on unfamiliar territory and writing a brief around the wrong
  assumptions — costs a full batch of rejected work to discover.
- A card without a "DONE MEANS" line — the worker invents its own definition of done, and
  it usually doesn't match yours.
- Over-specifying the brief to the point it constrains a path the orchestrator would have
  found on its own. Short briefs beat long ones; you're hiring a manager, not programming a
  robot.

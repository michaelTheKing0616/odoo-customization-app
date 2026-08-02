# PIPELINE.md — Loop & Team Architecture (all Cursor models)

Two views of the same system. The **loop view** (five steps) is the mechanical cycle any
single task goes through. The **team view** (four seats) is how that cycle gets distributed
across cheap and expensive models so it scales without scaling cost linearly. Read both —
most failures come from having one without the other.

```
Layer 4  Self-improvement   grade → distill → write back (skills/, ERRORS.md)
Layer 3  Memory             AGENTS.md, MEMORY.md, ERRORS.md, STATE.md
Layer 2  Orchestration      brief → card → gate → checker → judge → stop
Layer 1  Primitives         models, worktrees, terminal, Cursor CLI
```

## Layer 1 — Primitives

- Any Cursor-connected model (Composer 2.5, Opus 4.8, Sonnet 5, GPT-5.5 Codex, etc.) in
  Composer/Agent mode.
- Terminal access, `git worktree`, test runners, linters, build scripts — these are the
  actual "gate" (Layer 2), not the models.
- Cursor CLI for anything Composer-2.5-specific that needs to run outside the IDE, since
  Composer 2.5 has no public API.
- The provider API directly, for API-reachable models, when a genuinely separate checker
  context is needed without opening a second Cursor tab.

Primitives alone are "prompt it, it works for five minutes, close the tab." Nothing here
compounds without Layer 2 wrapped around it.

## Layer 2 — Orchestration

### The five-step loop

Every task, run by hand or delegated, goes through the same cycle:

1. **Discover** what needs doing.
2. **Plan** how to do it.
3. **Execute** the work.
4. **Verify** against a real, mechanical check (the gate — RULES.md Rule 4) plus, where
   judgment is needed, an independent checker (RULES.md Rule 6).
5. **Iterate** if not there yet — feed the structured gap back in and repeat, capped by a
   hard iteration limit (RULES.md Rule 7).

Skipping step 4's mechanical half is the single most common failure: without something that
can *objectively* fail the work, this is a model agreeing with itself on repeat, not a loop.

### The four seats

- **Orchestrator** — plans, splits, integrates, verifies at the end. Never does grunt work.
- **Workers** — cheap tier, one narrow task each, own clean context, own folder/branch.
- **Checker** — fresh context, strict pass/fail against the original spec, zero exposure to
  how the work was made. Rejects and states why; never fixes.
- **Judge** — for autonomous/looping runs, reads proof (diff, test result, file list), not
  claims of "done." Prevents an agent from declaring victory on a half-finished job.

### The brief (what you hand the orchestrator)

Four parts, every time — a vague brief is the actual root cause of most bad output, not a
weak model:

```
CONTEXT: what this is, who it's for, why it matters.
REQUEST: the outcome, not the steps.
OUTPUT FORMAT: exactly what lands on disk — files, structure, naming.
CONSTRAINTS: what it must not break on its own (stack, tone, budget, files off-limits).
```

Add the checkpoint clause so autonomy stays safe without becoming chatty:

```
Run this end-to-end. Use as many subagents/sessions as the job requires.
Pause for me only when it genuinely matters: spending money, sending
anything external, or a judgment call only I can make.
Otherwise don't stop. Show me the finished work when it's done.
```

Before writing the brief on anything non-trivial or in unfamiliar territory, have the
orchestrator pull ambiguity out of you first:

```
Interview me, one question at a time, about anything ambiguous in this
task. Prioritize questions where my answer would change the plan.
Stop when you could write the brief yourself.
```

### The card (what the orchestrator hands each worker)

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

Workers see only their own card, never the whole plan — this is what keeps context windows
small and keeps two workers from stepping on each other's assumptions.

### Two shapes — pick per task, not per project

- **Fan-out (parallel)** — subtasks don't touch each other. E.g. scaffolding `apps/web` and
  `apps/api` in separate worktrees, or writing independent Jinja templates for models vs
  security CSV. Each worker gets its own clean context; results synthesize at the end.
- **Pipeline (sequential)** — one worker's output is the next worker's input, each stage a
  fresh context that sees only the previous stage's deliverable, not its chat history. E.g.
  builder → tester (tests against the *spec*, not the code) → fixer (fixes only what the
  tester flagged, no drive-by refactoring) → documenter. Any stage failing twice = stop and
  report, don't push through.

Two workers never write to the same file in either shape — own folder or branch, always
(RULES.md Rule 5).

### The barbell (economics)

```
first ~10%:  orchestrator (expensive tier) plans and writes the briefs/cards
middle ~80%: workers (cheap tier) do the volume
last ~10%:   orchestrator (expensive tier) verifies the result against the original spec
```

Write the routing rule once and let the orchestrator apply it every run:

```
- planning, task-splitting, final verification: orchestrator, high effort
- drafts, variants, formatting, boring edits: cheap-tier worker
- anything needing real reasoning inside a subtask: mid-tier worker
- never use the premium tier for work a cheap tier passes the checker with
- log which tier did each task; if a cheap tier keeps failing the checker
  on a task type, promote that task type one tier and note it
```

An orchestrator-plus-parallel-workers setup beats the same model working alone by a wide
margin on tasks that split cleanly — but at meaningfully higher token cost. The barbell
exists to keep that multiplier from eating the quality gain; if you're not tracking cost per
accepted result (RULES.md Rule 13), you won't notice when it stops paying off.

## Layer 3 — Memory

See RULES.md Rule 9 for the four-file split (`AGENTS.md`, `MEMORY.md`, `ERRORS.md`,
`STATE.md`). The templates are in this package's root. The discipline that actually matters:
read all three (besides AGENTS.md, which is auto-loaded) at session start, write to
whichever changed at session end — every time, not just on "big" sessions.

## Layer 4 — Self-improvement

- **Grade.** After the gate/checker pass, ask explicitly: does this reveal a gap in an
  existing skill, or a new rule worth keeping? Not every pass/fail is worth recording, only
  ones that generalize.
- **Distill.** Turn a specific finding into a rule general enough to apply to future tasks.
  "The rating engine broke on player X" isn't a rule. "Era-normalization must clip outlier
  seasons before computing z-scores, or a single anomalous season skews the whole cohort" is.
- **Write back.** Commit the distilled rule to the relevant `skills/*.md` file, and log the
  event as a one-line retro at the end of each session:
  ```
  Run a retro on this session. Write into STATE.md:
  - what shipped, with links/paths
  - what failed and why, one line each
  - one rule to add to skills/ or AGENTS.md so this failure can't repeat
  Keep it under 15 lines. Next session reads this first.
  ```

## The five failure modes (know these before you scale)

- **The echo chamber.** No checker, or a checker too polite to fail anything. Everything
  passes; three days later the whole batch turns out to be mediocre. Fix: a real, separate
  checker seat (RULES.md Rule 6).
- **The early victory lap.** A worker or the loop itself declares done on a half-finished
  job and the orchestrator believes it. Fix: claims don't count, deliverables do — the judge
  reads a diff/test result/file list, never a sentence claiming success.
- **The token fire.** Every worker re-reading the whole project every pass. Fix: workers get
  narrow card-scoped context; only the orchestrator holds the full map.
- **The same-file collision.** Two workers, one file, silent overwrite. Fix: own
  folder/branch per worker, always (RULES.md Rule 5).
- **The team that shouldn't exist.** Overhead (briefs, handoffs, checks) exceeds the value
  for a task that fits in one prompt and one sitting. Fix: RULES.md Rule 14 — check the four
  conditions before building anything.

## Practical Cursor implementation notes

- `.cursorrules` at the repo root should inline or `@`-reference `RULES.md` so every session
  inherits the defaults and org-chart discipline automatically, regardless of model.
- For a genuinely independent checker: don't just open a second tab on the same
  conversation. New chat with no shared history (works for any model), or a scripted
  provider-API call (API-reachable models only — not Composer 2.5).
- Scheduled/triggered automation: GitHub Action/cron hitting the provider API for
  API-reachable models; Cursor CLI invocation in the same infrastructure for Composer 2.5.
- No Cursor agent harness handy? The same discipline works in a single chat by making one
  model play two roles in strict sequence — weaker than real separate contexts, but still
  catches more than no separation at all:
  ```
  We work in two roles, strictly separated.
  ROLE A - MAKER: produce the work for the task below.
  ROLE B - CHECKER: a different specialist who did NOT make the work.
    Grades only against the criteria. Brutal, pass/fail per criterion.
  PROTOCOL: MAKER produces → print "HANDOFF" → CHECKER grades →
    any FAIL = MAKER fixes only what failed → repeat.
  Stop only when every criterion passes. Never let the MAKER grade.
  ```
- Build order, every time: get one manual run reliable by hand → save it as a skill →
  wrap it in a loop with a gate and stop condition → only then put it on a schedule.
  Skipping straight to "scheduled" is how a loop burns money unattended before anyone
  catches the missing gate.
- Treat this whole package as itself subject to Layer 4: if a rule turns out wrong or
  incomplete for how this Odoo customization platform actually works, that's a lesson —
  distill it and edit the rule, don't just work around it silently.

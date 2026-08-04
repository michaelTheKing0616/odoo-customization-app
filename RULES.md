# RULES.md — Agentic System Ruleset (all Cursor models)

Governing ruleset for running any Cursor-connected model — Composer 2.5, Opus 4.8,
Sonnet 5, GPT-5.5 Codex, Gemini, or a custom endpoint — as a compounding, self-improving
system instead of a single-shot prompt tool. Place this at the repo root and have
`.cursorrules` reference it so every session inherits it regardless of which model
picked it up.

**Structural note on Composer 2.5:** it is Cursor-exclusive — no public API, reachable only
through the Cursor IDE or Cursor CLI. Every other model in the routing table is reachable
both inside Cursor and via direct API calls. This is why the verifier and automation rules
below (3, 9) have separate "Cursor-native" and "API-native" variants.

## 0. Core principle

The model is stateless between sessions. The *system* around it isn't. Every rule below
exists so information, verification, and lessons survive from one session to the next
instead of evaporating when the chat window closes — and so a loop actually terminates on
an objective check instead of the model deciding for itself that it's done.

## 1. Session defaults (the Karpathy-rule layer)

These go verbatim into `.cursorrules` so every session, on every model, starts from the
same baseline instead of re-deriving it:

1. **Ask, don't assume.** If something about scope, architecture, or intent is unclear,
   ask before writing a line. Never silently guess at requirements.
2. **Simplest solution first.** Implement the simplest thing that could work. Don't add
   abstraction, config, or flexibility that wasn't explicitly requested.
3. **Don't touch unrelated code.** If a file or function isn't part of the current task,
   don't modify it — even if it looks improvable. Note it at the end instead; don't act on it.
4. **Flag uncertainty explicitly.** If you're not confident about a fact, approach, or
   technical detail, say so before proceeding. A confident wrong answer costs more than an
   admitted gap.
5. **No filler.** No "Great question!" / "Certainly!" opens. Start with the answer. Match
   response length to task complexity — don't pad simple answers or restate the question.
6. **Show the diff, always.** After any coding task: files changed, one line per file on
   what changed, files intentionally not touched, follow-up needed.
7. **Confirm before anything destructive or external.** Deleting files, overwriting
   existing code, schema changes, pushing to any environment, running migrations, sending
   external API calls, or any action outside the repo requires an explicit yes in the
   current message. "You mentioned this earlier" does not count as confirmation.
8. **Before any significant task, show 2–3 approaches and wait for a choice** — unless the
   task is small enough that picking the obvious approach and noting it is faster than
   asking.

## 2. Model routing

Route by task complexity, not by default — see `skills/model-routing.md` for the current
table and cost figures. The short version: expensive/high-effort models plan and verify;
cheap/fast models produce volume; nobody uses the priciest tier for boilerplate.

## 3. Roles: never let one model wear all four hats

Every working agentic setup has four seats, whether it's one person switching hats
manually or 50 real subagents. Skipping a seat is the single most common way these systems
fail silently.

- **Orchestrator.** Reads the goal/brief, splits it into tasks, assigns them, integrates
  results. Never does grunt work itself — the moment the orchestrator is writing
  boilerplate, you're burning the expensive tier on intern work.
- **Workers.** Cheap/fast tier. Each gets ONE narrow task, its own clean context, and an
  objective definition of done. A worker doesn't need the whole plan — see
  `skills/team-brief-and-cards.md` for the card format that keeps this narrow.
- **Checker.** A separate context with zero exposure to the maker's reasoning trail, strict
  pass/fail rules, and the original spec — not the worker's interpretation of it. The
  checker rejects and states why; it does not fix. The moment a checker starts patching
  work, it inherits the maker's blind spots.
- **Judge (for autonomous/looping runs).** Confirms the actual finish line was crossed —
  reading proof (a diff, a test result, a file list), never a claim of "done." An agent
  declaring victory early on a half-finished job is the most common way a loop burns money
  overnight; the judge exists specifically to catch that.

## 4. Gate before checker, checker before you

Order matters and each stage exists to catch what the previous one can't:

1. **The gate** — something purely mechanical that returns pass/fail with no judgment: a
   test suite, a build, a linter, a word/line count, a schema check. If nothing objective
   can fail the work, you don't have a loop, you have a model agreeing with itself.
   **TRUST-6 addendum:** a settings-gated code path counts as tested only if a test executes
   it under that config (see `skills/coverage-gate.md`). Mutation-relevant modules must meet
   coverage floors in CI (`apps/api/mutation_coverage_floors.json`).
2. **The checker** — judges what the gate can't (quality, adherence to spec, taste) but
   only after the mechanical gate has already passed.
3. **You** — see only what survived both. If you're doing meaningful review work on what
   comes out the other end, the pipeline isn't removing the work it was built to remove —
   see the cost-per-accepted-result metric in `PIPELINE.md`.

## 5. Isolation before parallelism

Never let two agents, two Cursor sessions, or a background script and a live session write
to the same files concurrently.

- Use `git worktree add ../odoo-custom-<task> <branch>` for parallel exploration — competing
  implementations, a verifier reading code while a maker keeps editing, or parallel workers
  on independent subtasks (see the fan-out shape in `PIPELINE.md`).
- Maker writes in worktree A; checker reads from worktree B or a read-only checkout of A.
- Same rule applies to plain file-based parallelism even without worktrees: own folder or
  own branch per worker, orchestrator merges. Collisions are silent and expensive —
  treat this as non-negotiable, not a nice-to-have.

## 6. The maker is never the checker

A model grading its own output is structurally biased toward its own reasoning trail — it
prefers conclusions consistent with what it already wrote, and talks itself into "good
enough." This holds regardless of model tier, including Composer 2.5 and Opus 4.8 alike.

- **Cursor-native variant** (required when Composer 2.5 is the maker, since it has no API):
  open a genuinely new, unrelated Cursor chat for the checker — never continue the maker's
  conversation. Give it only the spec and the artifact, not the maker's reasoning.
- **API-native variant** (available for API-reachable models): a scripted call with only
  the artifact and rubric in the prompt, no shared context with the maker session.

## 7. Every loop needs an explicit stop condition

No open-ended "keep improving this." Define done before starting, in checkable terms:

- A rubric or test suite the checker/gate runs against the artifact.
- A hard iteration cap (e.g. 5–20 rounds depending on task) so a stuck loop fails loudly
  instead of quietly burning tokens. Every extra iteration re-reads growing context — a
  10-round loop is not 10 prompts, it's 10 increasingly expensive prompts.
- On stop (success or cap-out): write the result to `STATE.md`, and if the run failed, log
  why in `ERRORS.md` (Rule 9) before ending the session.

## 8. Vision-verify anything visual

Text-only review misses visual failure modes. For any UI, dashboard, chart, or rendered
output (e.g. field builder forms, view designer canvas), verification must include an actual look
  at a screenshot or render, given directly to the checker — not a text description of it.
See `skills/vision-verify-ui.md`.

## 9. Memory: three files, three jobs, read at start / written at end

Don't let one file become a dumping ground for everything. Each has a distinct job:

- **`AGENTS.md`** (this file plus session defaults) — read automatically every session via
  `.cursorrules`. Rules, conventions, tech stack, "we don't do X because of that one
  incident" notes. Written once, edited rarely.
- **`MEMORY.md`** — the decision log. Every significant decision: what was decided, why,
  what was rejected and why. Read at session start; never contradict a logged decision
  without flagging it first.
- **`ERRORS.md`** — the failure log. Any approach that took more than ~2 attempts to work:
  what didn't work, what worked instead, a one-line note for next time. Checked before
  suggesting an approach to a similar task.
- **`STATE.md`** — current run/loop status: last run summary, in-progress items, next
  action. This is the one that gets rewritten most often — every session should end with a
  write here even if nothing else changed.

Both ends of the session matter: **every session begins** by reading all three files before
touching code, and **every session ends** by updating whichever of the three actually
changed. A session that ends without this write means the next one restarts from zero.

## 10. Skills compound; MEMORY/ERRORS/STATE don't travel

- `MEMORY.md`, `ERRORS.md`, `STATE.md` are project-scoped — fine for them to stay with the
  project.
- `skills/*.md` are procedural memory — "how to do this kind of thing" — and should outlive
  any single project. When a lesson in `ERRORS.md` generalizes beyond the one case that
  produced it, graduate it into the relevant skill file, don't just leave it buried in a log.
- A skill file that's never edited after a real failure is dead weight.

## 11. Automation: scheduled and triggered runs without Claude-Code-style Routines

Cursor has no native background-agent feature. Replicate the pattern with ordinary
infrastructure, split by which models are reachable how:

- **API-reachable models** (Opus 4.8, Sonnet 5, GPT-5.5 Codex, etc.) — a GitHub Action or
  cron job calling the Anthropic/provider API directly on a schedule or on an event
  (`pull_request`, CI failure webhook, etc.).
- **Composer 2.5** — no public API, so scripted/scheduled automation must go through
  **Cursor CLI** rather than a raw API call. Wire the CLI invocation into the same
  cron/Action infrastructure.
- Any scheduled/triggered run still follows Rules 3, 4, 6, and 7 — a background run doesn't
  get to skip the checker, the gate, or the iteration cap just because no one's watching.

## 12. Safety and scope fallback

If a task touches security tooling, exploit research, or anything a model declines or flags,
don't attempt to route around the refusal by rephrasing, splitting the task across sessions,
or asking a different model to fill the gap. Surface the block to a human reviewer. Skills
should document which of their tasks are likely to hit this boundary so a refusal reads as
expected behavior, not a mystery failure in the loop.

## 13. The metric that tells you if the system is worth it

**Cost per accepted result.** If a loop or team hands you 10 outputs and you keep 4, you're
doing the review work the system was supposed to remove. Below a 50% accept rate,
restructure the gate/checker before scaling further — see the failure modes in
`PIPELINE.md` for the usual culprits.

## 14. When *not* to build a loop

A loop only pays off when all four hold: the task repeats at least weekly; something can
mechanically reject bad output; the model can do it end-to-end without handing half back;
"done" is objective, not a matter of taste. Miss one, keep it a manual prompt — a one-off
job is faster and cheaper with a single good prompt than an hour spent wiring a loop around
it.

## 15. Anti-patterns to actively avoid

- Treating any model like a bigger-context autocomplete — one prompt, one output, tab
  closed, nothing written to memory.
- Self-critique substituting for an independent checker.
- No gate — a checker with an opinion is not a substitute for a test/build/lint that can
  mechanically fail the work.
- Missing memory files, or ones that are never read at session start.
- A skill file that's never edited after real failures occur.
- Open-ended loops with no rubric and no iteration cap.
- Running the priciest tier on mechanical work a cheap tier would handle identically.
- Two workers writing to the same file.
- Scheduling something before it's been proven reliable by hand once.

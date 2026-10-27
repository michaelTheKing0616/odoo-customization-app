# 05 Packets: the only things that pass between roles

Each role receives **the card + the previous packet**, never the previous session's reasoning. Packets are plain text in the exact shape below and are pasted into `STATE.md` § Packets (newest first; trim to the last 20). Over the line limit = the packet is rejected and re-written.

## Dispatch (Orchestrator → any role), ≤ 8 lines

```
DISPATCH <card-id> · role: Oracle|Worker|Tester|Reviewer · tier: L1|L2|L3|E1 · loop: n/2
card: docs/build-plan/cards/phase-N/<ID>.md
context: .cursor/skills/ingenium-ui-excellence/SKILL.md   (UI sessions only: first item; load the main-tree file in full before any work)
floor: docs/design/UI_DIRECTION.md · docs/design/bar/xray-floor.png   (ui-spec and ui-build: read both; the floor is the minimum; beat it)
locks: <file set from the card's allow-list>   (STATE.md lock table row id)
budget: <class> · this role cap <tokens> · stop at 80%
input packet: <previous packet, pasted below, or "none">
rules: .cursorrules + 01_TOKEN_CHARTER.md + 02_INVARIANTS.md. Do only this card.
```

## Oracle packet (Oracle session → Orchestrator), ≤ 10 lines

```
ORACLE <card-id>
tests: <paths created>            (locked from now; Worker may not edit)
cases: <n> (one per AC + negatives) · source: card ACs | ORACLES.md §x
red: <command> → <n failed, 0 passed>   (must be red before the Worker starts)
ambiguities: none | <AC id: question>  (any ambiguity → Orchestrator asks Tope or amends card; never guess)
```

## Worker packet (Worker → Tester), ≤ 15 lines

```
WORKER <card-id> · loop n
files: <git diff --stat output, read-only>
outside allow-list: none            (anything else = automatic CHANGES)
commands for Tester:
  <exact command 1>  → expect <result>
  <exact command 2>  → expect <result>
ACs self-check: AC1 ✓ · AC2 ✓ · AC3 ? (<why>)
ui: §1 Step 7 of .cursor/skills/ingenium-ui-excellence/SKILL.md, every line filled, or n/a
risks: <≤ 2 lines>
oracles edited: no
```

## Tester packet (Tester → Reviewer), ≤ 15 lines

T0 runs every command; a model only interprets the script summary.

```
TESTER <card-id> · loop n · verdict PASS|FAIL
| AC | result | evidence |
| AC1 | pass | apps/api/tests/test_x.py::test_y |
| AC2 | fail | test_z: <one-line cause> |
guards: tsc ✓ lint ✓ jargon ✓ contrast ✓ hydration n/a plan_lint ✓
live: n/a | 17 ✓ 18 ✓ 19 ✓ 20 ✓ (ingenium_* dropped: yes)
order: random-order rerun ✓
label proposal: [Done, code] | [Done, live]
evidence files: <paths>
```

## Reviewer packet (Reviewer → Orchestrator), ≤ 10 lines

Exactly one verdict.

```
REVIEW <card-id> · APPROVE
```
```
REVIEW <card-id> · CHANGES
1. apps/api/app/x.py:120, why
2. … (max 5 items, each file:line, why)
```
```
REVIEW <card-id> · ESCALATE · <reason: e.g. oracle contradicts AC2; needs E1 fix note>
```

The Reviewer checks: every AC has evidence; no scope creep or file outside the allow-list; INV-01..18; write-gate / money-guard / auth impact; tests would fail if the feature were broken; UI checklist (`07_UI_EXCELLENCE_PROTOCOL.md` §6) for UI cards; token-charter compliance. For ui-spec and ui-build, the Reviewer also puts the contact sheet beside `docs/design/bar/xray-floor.png` and rates states, density and hierarchy, dark mode, 390 px, and copy each as at, above, or below the floor. Any "below" is CHANGES. Patterns come from `docs/design/UI_DIRECTION.md`. The main stream aims to beat the floor.

## Close-out (Orchestrator, T0 script where possible), ≤ 6 lines

```
CLOSE <card-id> · <date>
PROGRESS: <date> · <card> · <command> · <counts> · <label>     (appended to apps/api/evals/v2/PROGRESS.md)
ledger: <row ids> → status <label>
locks released: <row id> · tokens: W <n> T <n> R <n> (O <n>) vs cap
facts: none | FACTS.md +1 line
```

## E1 fix note (E1 → next Worker), ≤ 25 lines

```
FIXNOTE <card-id> · after <n> loops at <tier>
root cause: <≤ 3 lines, with file:line evidence>
change: <exact symbols and the change, as steps; no code unless a 5-line snippet is clearer>
do not: <the approach that failed>
verify: <command> → <expected>
```

## Ask Tope (Orchestrator → Tope), ≤ 15 lines, batched

```
ASK · <date> · <n> items (each blocks a named card)
1. <card/DEC id>: <question> · default: <recommended answer> · blocks: <cards>
```

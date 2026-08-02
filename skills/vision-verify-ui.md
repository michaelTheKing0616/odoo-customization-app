# Skill: Vision-Verify for Visual Output

## When to use
Any task producing something visual — field/model builder forms, view designer canvas,
automation rule builder, onboarding screens — where "the code looks right" isn't the same
claim as "the rendered result looks right."

## How
1. Maker implements the change and produces a screenshot/render of the result (e.g. a
   headless browser screenshot, a saved chart image).
2. Verifier session (see `verifier-subagent.md`) receives the image directly, plus:
   - the original goal/design description in plain text
   - any relevant design tokens or reference screenshots from prior sessions (pull the
     "Last session" / prior screenshot reference from `STATE.md` if one exists)
3. Verifier compares directly against the image, not against a text description of the
   image. If the model can't be shown the image in that context, this step doesn't count as
   done — a text-only pass is not a substitute.
4. On mismatch, verifier states the gap in concrete terms ("spacing between cards is
   inconsistent, card 3 overflows container at widths below 480px") rather than a general
   impression.

## Known failure modes
- Skipping this for "just a small CSS change" — small visual regressions are exactly what
  text-only review misses.
- Comparing against a stale reference screenshot instead of updating it after intentional
  redesigns.

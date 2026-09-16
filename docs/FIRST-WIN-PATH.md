# First-win path (≤8 minutes after connect)

Target journey after a successful connection probe:

1. **Connect** (`/connect`) — credentials → probe → summary card (`data-testid="connect-first-win"`).
2. **App Studio** — primary CTA (`connect-first-win-app-studio`). Describe work; no live write until human Promote.
3. **Projects** — optional board for the draft (`connect-first-win-projects`).
4. **Overview** — full model map when needed (`connect-first-win-overview`).

Overview empty-state (`FirstRunCard`) mirrors the same order: App Studio → Projects → Builder.

## Manual timing checklist
- [ ] Fresh connect on a known Odoo URL
- [ ] Open App Studio from the success card
- [ ] Submit a one-sentence brief and reach a reviewable draft
- [ ] Stop before Promote (human gate)
- [ ] Wall clock from “Connection saved” ≤ 8 minutes

Record date + result in `docs/UAT-PREMIUM-WORLD-CLASS.md` when re-UAT runs.

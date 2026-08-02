# COPY GUIDE — product voice, terminology, and message templates

Binding for every user-facing string. Models do not invent terminology or tone. When a card
says "COPY_GUIDE template", the exact structures below are used.

## Voice

Plain, confident, honest. Start with the fact or the action. No filler, no hype, no apology
theater. Technical terms are used precisely and consistently — never synonyms.

Rules:
- Sentence case everywhere (buttons, titles, labels): "Create field", not "Create Field".
- Buttons are verb-first and specific: "Create field", "Apply to Odoo", "Run dry-run",
  "Snapshot now". Never "Submit", "OK", "Yes", "Continue" (except wizard next-steps:
  "Next: review draft").
- Destructive actions state scope in the label or immediately beside it:
  "Delete 214 records", "Uninstall module (removes 3 models)".
- No exclamation marks in system copy. No emoji anywhere in product UI.
- No "Oops", "Uh oh", "Something went wrong" alone — errors always name the thing and the
  recovery.
- Numbers are real: "5 of 214 failed", never "some records failed".

## Glossary (locked — the only allowed terms)

- **Connection** — a linked Odoo instance.
- **Draft** — an unapplied ModuleSpec (AI or manual). Never "generation", "result", "output".
- **Apply** — writing a draft/spec to a connection live (metadata path).
- **Export** — producing an installable module zip.
- **Sandbox** — the ephemeral test Odoo. "Sandbox run" = install validation.
- **Promote** — installing a validated module on a target connection.
- **Snapshot** — a saved restore point. **Rollback** — restoring one.
- **Recipe** — a predefined Power Ops/bulk operation.
- **Dry-run** — preview of a bulk/apply operation with zero writes.
- **Workspace** — the billing/team container (MON).
- **Internal** — the unlimited testing plan (admin only).
- Tiers by name: **Solo**, **Pro**, **Business**, **Agency**.
- Hosting kinds: **Odoo Online**, **Odoo.sh**, **self-hosted** (+ edition: Community /
  Enterprise).

## Capability-gating template (Doc 6 three-options rule)

Every gated feature renders a Callout with exactly three parts. Never hide the feature.

```
[Title] <Feature> isn't available on this connection
[Why — one sentence, specific]
  e.g. "Automation rules need the base_automation module, which isn't installed on this
  Odoo Online instance (it ships with Odoo's Custom plan)."
[Options — 1 to 3 concrete paths, each one line]
  - "Upgrade the Odoo subscription to the Custom plan to unlock live automations."
  - "Deploying to Odoo.sh or self-hosted? Export this as a module with scheduled actions
    instead."
  - "Or leave automations out — everything else here works fully."
```

Subscription-tier gating (our tiers) uses the same shape:
```
[Title] Bulk operations are on the Business plan
[Why] "Your workspace is on Pro."
[Options] "Upgrade to Business" (primary) · "See what Business includes"
```

## Honesty labels (fixed strings)

- Sandbox on Online targets: "Approximate validation — this sandbox is a clean Odoo
  <version>, not a copy of your instance. Differences in installed apps or data can still
  cause conflicts."
- Rollback reversibility: "Fully reversible" / "Partially reversible — <what can't come
  back>".
- Recompute unavailable: "This fix needs server shell access, which <hosting> doesn't
  provide. No changes were made. If you have an Odoo.sh or self-hosted copy, run it there."
- Enterprise pending verification: "Built against Odoo's public documentation — not yet
  verified against a live Enterprise instance."
- Barcode module: "Scanning inside Odoo forms uses our add-on module — it's our code, not a
  built-in Odoo feature. In-app scanning works on every plan without installing anything."

## Empty states (one teach-line + one action)

Format: `<What this is, one sentence>. <Primary action>.`
- Automations: "Automations react to record changes — update fields, send emails, schedule
  activities. Create your first automation."
- Snapshots: "Snapshots are restore points taken before risky changes. They appear here
  automatically — or take one now."
- Draft Studio: "Describe the app you need and get a reviewable draft — nothing touches
  Odoo until you apply it. Describe your app."
- Bulk Suite: "Run permitted operations across hundreds of records at once — every record
  is checked by Odoo's own rules. Pick a model to start."
- Expert: "Ask anything about Odoo or this instance. Answers cite their sources — and say
  so when they don't know."

## Error + recovery pattern

`<What failed, specifically>. <Why, if known>. <Recovery action(s)>.`
- "Couldn't reach your Odoo instance (connection timed out). Check the URL and that the
  instance is up, then retry." [Retry] [Edit connection]
- "Apply stopped: field x_status references selection value 'closed' that doesn't exist.
  Fix the draft or re-run the dry-run." [Open draft] [Run dry-run] [Diagnose with Expert]
- Partial bulk failure: "487 of 500 records updated. 13 were rejected by Odoo (locked
  period). Review the failed rows below." — never aggregate-only.

## Confirmation dialogs (destructive)

Title: the action + scope ("Delete 3 fields from x_matter"). Body: consequences list
(bulleted, concrete), snapshot line ("A snapshot was taken — ID #123" or "This cannot be
rolled back: <why>"), phrase-confirm input where the existing gates require it. Primary
button = the destructive verb, danger-styled; secondary = "Cancel".

## Trial/billing copy

- Trial banner (≤3 days): "Business trial ends in <n> days. Keep bulk operations, health
  checks and the Expert — choose a plan."
- Downgrade summary: "Moving to <plan> re-locks: <feature list from registry>. Your data,
  drafts and history stay intact."
- Payment failure: "Payment didn't go through. Your plan stays active until <date> — update
  the card in the billing portal."

## Microcopy details

- Loading: skeletons, no text; long jobs show step names ("Installing module in sandbox…").
- Tooltips on icon-only buttons: the action verb ("Snapshot now").
- Timestamps: relative under 7 days ("3h ago"), absolute date after.
- Keyboard hints as Kbd chips, not text ("Press ⌘K").

/** COPY_GUIDE empty-state and honesty strings — single source for product copy (UIX-5). */

export const EMPTY_STATES = {
  automations:
    "Automations react to record changes — update fields, send emails, schedule activities. Create your first automation.",
  snapshots:
    "Snapshots are restore points taken before risky changes. They appear here automatically — or take one now.",
  draftStudio:
    "Describe the app you need and get a reviewable draft — nothing touches Odoo until you apply it. Describe your app.",
  bulkSuite:
    "Run permitted operations across hundreds of records at once — every record is checked by Odoo's own rules. Pick a model to start.",
  expert:
    "Ask anything about Odoo or this instance. Answers cite their sources — and say so when they don't know.",
  journal:
    "Snapshots are restore points taken before risky changes. They appear here automatically — or take one now.",
  projects: "Create a draft from a template or start blank, then edit in ModuleSpec.",
} as const;

export const REVERSIBILITY = {
  yes: "Fully reversible",
  partial: "Partially reversible — some fields or side effects may remain",
  none: "Not reversible — undo is disabled for this snapshot",
} as const;

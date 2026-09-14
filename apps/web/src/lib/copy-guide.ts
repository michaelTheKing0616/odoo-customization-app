/** COPY_GUIDE empty-state and honesty strings — single source for product copy (UIX-5). */

export const EMPTY_STATES = {
  builder:
    "Create an x_ model with default list, form, and search views, then add fields. Stock models stay available by technical name.",
  automations:
    "Automations react to record changes — update fields, send emails, schedule activities. Create your first automation.",
  menus:
    "Menus are the app switcher and navbar. Create a root or child item, bind a window action, and restrict visibility by group when needed.",
  access:
    "Access rights grant CRUD on a model. Record rules filter which rows a group can see or change. Start with a group-scoped ACL line.",
  snapshots:
    "Snapshots are restore points taken before risky changes. They appear here automatically — or take one now.",
  draftStudio:
    "Talk in plain language at any grain — a field on invoices, a feature under Sales, or a full practice app. Stock Odoo first; custom models only for the residual. Nothing touches Odoo until you Apply.",
  jobAutopilot:
    "Drop a brief and client files. Autopilot installs stock Odoo apps on a sandbox, customizes only the residual, loads data after a dry-run, then RPC-smokes quote→confirm→invoice (and Purchase/POS/CRM probes when those apps are in the packet). After smoke, download the Config Packet and apply the delta on the client connection with confirm — Autopilot itself still refuses production. Completeness 10.0 is not this bar.",
  bulkSuite:
    "Run permitted operations across hundreds of records at once — every record is checked by Odoo's own rules. Pick a model to start.",
  expert:
    "Ask anything about Odoo or this instance. Answers cite their sources — and say so when they don't know.",
  journal:
    "Snapshots are restore points taken before risky changes. They appear here automatically — or take one now.",
  projects:
    "Create a draft from a template or start blank, then review vs live and apply on a sandbox. Completeness is not go-live. Promote stays human.",
  moduleSpec:
    "Load a Draft Studio handoff, import a zip, or add an x_ model. Completeness is hygiene — not Certification or Autopilot.",
} as const;

export const REVERSIBILITY = {
  yes: "Fully reversible",
  partial: "Partially reversible — some fields or side effects may remain",
  none: "Not reversible — undo is disabled for this snapshot",
} as const;

/** Three independent bars — never fuse Completeness with Certification or Autopilot. */
export const SCORE_BARS = {
  completeness:
    "Completeness is ModuleSpec hygiene (fields, views, ACL) — not go-live.",
  certification:
    "Certification is the ship bar. Option A (PDF/QR/Pay/Python) stays Reject until sandbox prove.",
  autopilot:
    "Autopilot done-bar is RPC process smoke on the Job page — separate from Completeness and Cert. Promote stays human.",
  expertFix:
    "Expert closer repairs this JSON hygiene. It does not run Option A sandbox smoke or Autopilot, and will not raise Certification to Production.",
} as const;

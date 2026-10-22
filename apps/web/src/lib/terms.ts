/** Plain word → Odoo term + technical name (FEATURE_AUDIT: term hover card). One glossary source. */
export type TermEntry = {
  plain: string;
  odoo: string;
  tech: string;
  /** "Record type" (a model) or "Field". */
  kind?: "Record type" | "Field";
  /** Odoo app it lives in. */
  app?: string;
  /** One-line meaning in plain words. */
  meaning?: string;
  /** Version differences, newest last. */
  versions?: string;
  note?: string;
};

const T = (tech: string, plain: string, odoo: string, app: string, meaning: string, versions?: string): TermEntry => ({
  tech, plain, odoo, app, meaning, versions, kind: "Record type",
});

export const TERMS: Record<string, TermEntry> = {
  "res.partner": T("res.partner", "Contact", "Contact (Partner)", "Contacts", "A person or company you deal with: customers, suppliers, employees' addresses."),
  "res.users": T("res.users", "User", "User", "Settings", "Someone who can sign in to Odoo."),
  "res.groups": T("res.groups", "Access group", "Group", "Settings", "A role. People in it get the same rights.", "Odoo 19+ shows groups as 'Roles' in some screens."),
  "ir.model.access": T("ir.model.access", "Access rule", "Access Rights", "Settings (developer mode)", "Who can read, change, create or delete one record type.", "Odoo 20 renames it ir.access (fields model_id / group_id)."),
  "ir.rule": T("ir.rule", "Record rule", "Record Rule", "Settings (developer mode)", "Limits which records of a type a group can see or change.", "Odoo 20 folds record rules into ir.access."),
  "ir.ui.view": T("ir.ui.view", "Screen", "View", "Settings (developer mode)", "How a form, list or kanban looks."),
  "ir.ui.menu": T("ir.ui.menu", "Menu", "Menu Item", "Settings (developer mode)", "An entry in Odoo's menus."),
  "ir.actions.server": T("ir.actions.server", "Action", "Server Action", "Settings (developer mode)", "A step Odoo runs on records: update a field, send an email, run code."),
  "base.automation": T("base.automation", "Automation", "Automation Rule", "Settings (developer mode)", "Runs an action by itself when something happens or a date arrives.", "Odoo 17+ moved it into the Automation Rules app."),
  "ir.cron": T("ir.cron", "Scheduled job", "Scheduled Action", "Settings (developer mode)", "Something Odoo runs on a timer, like sending queued emails."),
  "ir.sequence": T("ir.sequence", "Numbering", "Sequence", "Settings (developer mode)", "How document numbers are made, like INV/2026/0001."),
  "ir.model.fields": T("ir.model.fields", "Field", "Field", "Settings (developer mode)", "One piece of information on a record."),
  "ir.model": T("ir.model", "Record type", "Model", "Settings (developer mode)", "A kind of record, like Contact or Sales Order. Odoo calls it a model."),
  "account.move": T("account.move", "Invoice or journal entry", "Journal Entry", "Accounting", "Invoices, bills and journal entries are all this one record type."),
  "sale.order": T("sale.order", "Sales order", "Sales Order", "Sales", "A quotation, and the order once it's confirmed."),
  "crm.lead": T("crm.lead", "Lead", "Lead/Opportunity", "CRM", "A possible sale, from first contact to won or lost."),
  "product.template": T("product.template", "Product", "Product", "Sales / Inventory", "Something you sell or buy. Variants share it."),
  "mail.template": T("mail.template", "Email template", "Email Template", "Settings (developer mode)", "A reusable email with placeholders filled from the record."),
};

/** Plain labels (any case, singular or plural) that must render inside <Term>. Used by the enforcing test. */
export const MAPPED_LABELS: Record<string, string> = {
  "record type": "ir.model", "record rule": "ir.rule", "access rule": "ir.model.access", "access rights": "ir.model.access",
  "scheduled job": "ir.cron", "scheduled action": "ir.cron", "server action": "ir.actions.server",
  "automation rule": "base.automation", "email template": "mail.template", "numbering": "ir.sequence",
  "access group": "res.groups", "sales order": "sale.order", "journal entry": "account.move",
};

export function lookupTerm(tech: string): TermEntry | undefined {
  return TERMS[tech];
}

/** Link to the record type's list in Odoo (developer mode), when the connection's URL is known. */
export function odooModelUrl(base: string | undefined, tech: string): string | undefined {
  if (!base) return undefined;
  return `${base.replace(/\/$/, "")}/odoo/action-base.action_model_model?debug=1#model=${encodeURIComponent(tech)}`;
}

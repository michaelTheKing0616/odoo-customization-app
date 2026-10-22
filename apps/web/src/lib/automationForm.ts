import type { AutomationActionKind, Connection } from "@/lib/api";
import { connectionSupports } from "@/lib/capabilities";

export const CONFIRM_PHRASE = "I understand the risks";

export const ADVANCED_ACTION_KINDS = new Set<AutomationActionKind>([
  "webhook",
  "sms",
  "followers",
  "remove_followers",
]);

export const SAFE_ACTION_KINDS: AutomationActionKind[] = [
  "update_field",
  "related_write",
  "create_activity",
  "create_record",
  "mail_post",
];

export type TriggerGroupId = "record" | "timed" | "message" | "advanced";

export type TriggerOption = {
  value: string;
  label: string;
  group: TriggerGroupId;
  hint: string;
};

export const TRIGGER_GROUPS: { id: TriggerGroupId; label: string }[] = [
  { id: "record", label: "Record events" },
  { id: "timed", label: "Timed" },
  { id: "message", label: "Messages" },
  { id: "advanced", label: "Advanced" },
];

export const TRIGGERS: TriggerOption[] = [
  {
    value: "on_create",
    label: "On create",
    group: "record",
    hint: "Runs once when a matching record is created.",
  },
  {
    value: "on_write",
    label: "On update",
    group: "record",
    hint: "Runs after a write. Optionally limit to specific fields.",
  },
  {
    value: "on_create_or_write",
    label: "On create and edit",
    group: "record",
    hint: "Runs on create and on later writes.",
  },
  {
    value: "on_unlink",
    label: "On deletion",
    group: "record",
    hint: "Runs when a matching record is deleted.",
  },
  {
    value: "on_archive",
    label: "On archived",
    group: "record",
    hint: "Runs when a record is archived (active set to false).",
  },
  {
    value: "on_unarchive",
    label: "On unarchived",
    group: "record",
    hint: "Runs when a record is unarchived.",
  },
  {
    value: "on_time",
    label: "Based on date field",
    group: "timed",
    hint: "Runs relative to a date or datetime field on the record.",
  },
  {
    value: "on_time_created",
    label: "After creation",
    group: "timed",
    hint: "Runs a delay after the record is created.",
  },
  {
    value: "on_time_updated",
    label: "After last update",
    group: "timed",
    hint: "Runs a delay after the record is last written.",
  },
  {
    value: "on_message_received",
    label: "On message received",
    group: "message",
    hint: "Runs when the record receives an incoming email.",
  },
  {
    value: "on_message_sent",
    label: "On message sent",
    group: "message",
    hint: "Runs when an email is sent from the record.",
  },
  {
    value: "on_webhook",
    label: "On webhook",
    group: "advanced",
    hint: "Runs when an incoming webhook hits this automation.",
  },
  {
    value: "on_change",
    label: "On UI change",
    group: "advanced",
    hint: "Runs in the form UI when the watched field changes.",
  },
];

export const ADVANCED_CONFIRM_COPY: Record<string, { warning: string; risks: string[] }> = {
  code_live: {
    warning: "Live Python executes immediately on this database.",
    risks: [
      "Live Python executes immediately on this database",
      "Can modify any data the Odoo user can access",
      "Undo restores automation definition — not business data side effects",
    ],
  },
  webhook: {
    warning: "Webhook automations POST record data to an external URL.",
    risks: [
      "May exfiltrate business data to a third party",
      "URL must be trusted; payloads can include selected fields",
      "Rollback removes the rule — not data already sent",
    ],
  },
  sms: {
    warning: "SMS automations send messages via the Odoo SMS provider.",
    risks: [
      "May incur carrier / IAP costs",
      "Messages go to phone numbers on matching records",
      "Rollback removes the rule — not messages already sent",
    ],
  },
  followers: {
    warning: "Follower automations change who follows records.",
    risks: [
      "Can subscribe partners without their explicit consent in-app",
      "May increase notification noise",
      "Rollback removes the rule — not follower links already added",
    ],
  },
  remove_followers: {
    warning: "Remove-followers automations unsubscribe partners from records.",
    risks: [
      "Users may stop receiving important notifications",
      "Hard to reverse at scale once applied",
      "Rollback removes the rule — not follower removals already done",
    ],
  },
};

export const LIBRARY_FINE_SNIPPET = `# Library fine on return — custom code (state=code in generated module / sandbox).
# Available: env, model, record, records, time, datetime, dateutil, timezone, log, Warning
for record in records:
    if not record.x_returned or not record.x_due_date:
        continue
    today = datetime.date.today()
    due = record.x_due_date
    days = max((today - due).days, 0)
    rate = (record.x_book_id.x_fine_rate if record.x_book_id else 0.0) or 0.0
    record.write({
        'x_days_overdue': days,
        'x_fine_amount': float(days) * float(rate),
    })
`;

export type AutomationComposerForm = {
  name: string;
  model: string;
  trigger: string;
  filter_domain: string;
  filter_pre_domain: string;
  trigger_field_names: string;
  action_kind: AutomationActionKind;
  field_name: string;
  value: string;
  relation_field: string;
  activity_type_id: number;
  activity_summary: string;
  trg_date_field_name: string;
  trg_date_range: number;
  trg_date_range_type: "minutes" | "hour" | "day" | "month";
  trg_date_range_mode: "after" | "before";
  target_model: string;
  field_values_text: string;
  mail_template_id: number | "";
  mail_post_method: "email" | "comment" | "note";
  mail_subject: string;
  mail_body_html: string;
  mail_email_to: string;
  webhook_url: string;
  webhook_field_names: string;
  sms_template_id: number | "";
  sms_body: string;
  sms_method: "sms" | "comment" | "note";
  partner_ids_text: string;
  followers_type: "specific" | "generic";
  followers_partner_field_name: string;
  python_code: string;
  module_technical_name: string;
};

export function defaultComposerForm(model = "res.partner"): AutomationComposerForm {
  return {
    name: "",
    model,
    trigger: "on_create",
    filter_domain: "",
    filter_pre_domain: "",
    trigger_field_names: "",
    action_kind: "update_field",
    field_name: "",
    value: "",
    relation_field: "",
    activity_type_id: 0,
    activity_summary: "Follow up",
    trg_date_field_name: "create_date",
    trg_date_range: 0,
    trg_date_range_type: "day",
    trg_date_range_mode: "after",
    target_model: "",
    field_values_text: "",
    mail_template_id: "",
    mail_post_method: "email",
    mail_subject: "",
    mail_body_html: "",
    mail_email_to: "",
    webhook_url: "",
    webhook_field_names: "",
    sms_template_id: "",
    sms_body: "",
    sms_method: "sms",
    partner_ids_text: "",
    followers_type: "specific",
    followers_partner_field_name: "",
    python_code:
      "# available: env, model, record, records, time, datetime, dateutil, timezone, log, Warning\nrecord.write({'x_auto_note': 'from code'})\n",
    module_technical_name: "custom_automation_code",
  };
}

export type AutomationSessionState = "draft" | "unsaved" | "saved";

export function composerSessionState(opts: {
  dirty: boolean;
  savedOnce: boolean;
}): AutomationSessionState {
  if (opts.dirty) return "unsaved";
  if (opts.savedOnce) return "saved";
  return "draft";
}

export function isComposerDirty(
  form: AutomationComposerForm,
  baseline: AutomationComposerForm,
): boolean {
  return JSON.stringify(form) !== JSON.stringify(baseline);
}

export function triggerLabel(value: string): string {
  return TRIGGERS.find((t) => t.value === value)?.label ?? value;
}

export function triggerHint(value: string): string {
  return TRIGGERS.find((t) => t.value === value)?.hint ?? "";
}

export function parseFieldValueLines(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    if (key) out[key] = value;
  }
  return out;
}

export function parseIdList(text: string): number[] {
  return text
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n > 0);
}

export function parseNameList(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function actionKindCapabilityId(kind: AutomationActionKind): string | null {
  if (kind === "update_field") return "object_write_update_path";
  if (kind === "related_write") return "related_write_dotted_path";
  if (kind === "create_record") return "object_create_crud_model";
  return null;
}

export function actionKindAvailable(
  connection: Connection | null | undefined,
  kind: AutomationActionKind,
): boolean {
  const cap = actionKindCapabilityId(kind);
  if (!cap) return true;
  return connectionSupports(connection, cap);
}

export function firstAvailableSafeActionKind(
  connection: Connection | null | undefined,
): AutomationActionKind {
  for (const kind of SAFE_ACTION_KINDS) {
    if (actionKindAvailable(connection, kind)) return kind;
  }
  return "create_activity";
}

export function designerHref(connectionId: string, model: string): string {
  const base = `/connections/${connectionId}/designer`;
  const trimmed = model.trim();
  return trimmed ? `${base}?model=${encodeURIComponent(trimmed)}` : base;
}

export function automationsHref(connectionId: string, model: string): string {
  const base = `/connections/${connectionId}/automations`;
  const trimmed = model.trim();
  return trimmed ? `${base}?model=${encodeURIComponent(trimmed)}` : base;
}


/** Live Python is never offered. Map legacy code_live onto Option A. */
export function coerceToOptionA(
  kind: AutomationActionKind,
): AutomationActionKind {
  return kind === "code_live" ? "python_module" : kind;
}

export type PromptDraftHints = {
  name?: string;
  model?: string;
  trigger?: string;
  action_kind?: AutomationActionKind;
};

/**
 * Deterministic prompt → composer hints. No network. Prefer safe actions;
 * Python language cues become Option A (python_module), never code_live.
 */
export function parseAutomationPrompt(raw: string): PromptDraftHints {
  const text = raw.trim();
  if (!text) return {};
  const lower = text.toLowerCase();
  const out: PromptDraftHints = {};

  const modelMatch = text.match(/\b(x_[a-z0-9_]+|[a-z][a-z0-9_]*\.[a-z0-9_]+)\b/i);
  if (modelMatch) out.model = modelMatch[1];

  if (/\bon create\b|\bwhen (a |the )?record is created\b/.test(lower)) {
    out.trigger = "on_create";
  } else if (/\bon (update|write|edit)\b|\bwhen .+ (is |are )?(updated|changed|written)\b/.test(lower)) {
    out.trigger = "on_write";
  } else if (/\bon delete|on unlink|when .+ deleted\b/.test(lower)) {
    out.trigger = "on_unlink";
  } else if (/\bafter (creation|create)\b|\bbased on date\b|\bschedule[d]?\b/.test(lower)) {
    out.trigger = "on_time";
  }

  if (/\bwebhook\b|\bhttp(s)?:\/\//.test(lower)) {
    out.action_kind = "webhook";
  } else if (/\bpython\b|\bcompute\b|\bfor record in records\b|\bstate\s*=\s*code\b/.test(lower)) {
    out.action_kind = "python_module";
  } else if (/\bactivit(y|ies)\b|\bschedule (a )?todo\b/.test(lower)) {
    out.action_kind = "create_activity";
  } else if (/\bemail\b|\bmail\b|\bnotify\b|\bmessage\b/.test(lower)) {
    out.action_kind = "mail_post";
  } else if (/\bcreate (a )?record\b|\bspawn\b/.test(lower)) {
    out.action_kind = "create_record";
  } else if (/\bupdate (linked|related)\b|\brelated write\b/.test(lower)) {
    out.action_kind = "related_write";
  } else if (/\bset |\bupdate (the )?field\b|\bwrite \w+\b/.test(lower)) {
    out.action_kind = "update_field";
  }

  const name = text.split(/[.\n]/)[0]?.trim() ?? "";
  if (name && name.length <= 80) out.name = name.replace(/\s+/g, " ");
  return out;
}

export const OPTION_A_PATH_STEPS = [
  { title: "Export module", detail: "Generate an installable zip with state=code inside the module." },
  { title: "Sandbox", detail: "Install and prove the module on a clean sandbox of the same major." },
  { title: "Promote", detail: "A human promotes to the target. Live Python never runs from this screen." },
] as const;

export function automationsEmptyGuide(hasFilter: boolean, query: string): {
  title: string;
  why: string;
  next: string;
} {
  if (hasFilter) {
    return {
      title: `No rule matches "${query}"`,
      why: "The filter checks rule names, models, and triggers only.",
      next: "Clear the filter, or create a new automation.",
    };
  }
  return {
    title: "No automations yet",
    why: "Automations react to record changes: update fields, send emails, schedule activities.",
    next: "Create your first automation from the composer.",
  };
}


export type AutomationStarter = { label: string; name: string; model: string; trigger: string; filter_domain: string };

const STARTER_RECIPES: { model: string; label: (n: string) => string; trigger: string; filter_domain: string }[] = [
  { model: "sale.order", label: (n) => `When a ${n} is confirmed`, trigger: "on_write", filter_domain: "[('state', '=', 'sale')]" },
  { model: "crm.lead", label: (n) => `When a new ${n} arrives`, trigger: "on_create", filter_domain: "" },
  { model: "account.move", label: (n) => `When a ${n} is posted`, trigger: "on_write", filter_domain: "[('state', '=', 'posted')]" },
  { model: "project.task", label: (n) => `When a ${n} is created`, trigger: "on_create", filter_domain: "" },
  { model: "helpdesk.ticket", label: (n) => `When a new ${n} arrives`, trigger: "on_create", filter_domain: "" },
  { model: "res.partner", label: (n) => `When a ${n} is edited`, trigger: "on_write", filter_domain: "" },
];

/** Touch 67: up to three starters built only from models this database really has (custom models first). Loading one fills the composer; nothing is saved until Create. */
export function automationStarters(models: { model: string; name: string }[], max = 3): AutomationStarter[] {
  const byModel = new Map(models.map((m) => [m.model, m.name?.trim() || m.model]));
  const out: AutomationStarter[] = [];
  for (const m of models) {
    if (out.length >= 1) break;
    if (!m.model.startsWith("x_")) continue;
    const n = byModel.get(m.model)!;
    out.push({ label: `When a new ${n} is created`, name: `New ${n}`, model: m.model, trigger: "on_create", filter_domain: "" });
  }
  for (const r of STARTER_RECIPES) {
    if (out.length >= max) break;
    const n = byModel.get(r.model);
    if (!n) continue;
    out.push({ label: r.label(n), name: r.label(n), model: r.model, trigger: r.trigger, filter_domain: r.filter_domain });
  }
  return out;
}

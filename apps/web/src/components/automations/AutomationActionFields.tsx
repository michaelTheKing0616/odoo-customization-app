"use client";

import { Callout } from "@/components/ui/Callout";
import { Disclosure } from "@/components/ui/Disclosure";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { ActivityTypeRow } from "@/lib/api";
import {
  ADVANCED_ACTION_KINDS,
  type AutomationComposerForm,
} from "@/lib/automationForm";

type MailTemplate = {
  id: number;
  name: string;
  model: string | null;
  subject: string | null;
};

type Props = {
  form: AutomationComposerForm;
  onChange: (patch: Partial<AutomationComposerForm>) => void;
  activityTypes: ActivityTypeRow[];
  mailTemplates: MailTemplate[];
};

export function AutomationActionFields({
  form,
  onChange,
  activityTypes,
  mailTemplates,
}: Props) {
  const kind = form.action_kind;

  return (
    <div className="space-y-4">
      {kind === "python_module" ? (
        <Callout variant="warning" title="Option A — exports as a module">
          Python runs only after module export, sandbox test, and explicit promote. It is
          not applied live from this screen.
        </Callout>
      ) : null}
      {ADVANCED_ACTION_KINDS.has(kind) ? (
        <Callout variant="warning" title="Advanced action">
          Creating this rule requires an Odoo-style confirmation. Prefer a safe action
          when it covers the job.
        </Callout>
      ) : null}

      {kind === "update_field" ? (
        <>
          <Input
            label="Field"
            required
            value={form.field_name}
            onChange={(e) => onChange({ field_name: e.target.value })}
            className="font-mono text-sm"
            placeholder="x_status"
            hint="Technical name on this model."
          />
          <Input
            label="Value"
            required
            value={form.value}
            onChange={(e) => onChange({ value: e.target.value })}
            placeholder="confirmed"
          />
        </>
      ) : null}

      {kind === "related_write" ? (
        <>
          <Input
            label="Relation field"
            required
            value={form.relation_field}
            onChange={(e) => onChange({ relation_field: e.target.value })}
            className="font-mono text-sm"
            placeholder="x_vehicle_id"
            hint="Many2one on this model that points at the record to update."
          />
          <Input
            label="Field on related record"
            required
            value={form.field_name}
            onChange={(e) => onChange({ field_name: e.target.value })}
            className="font-mono text-sm"
            placeholder="x_status"
          />
          <Input
            label="Value"
            required
            value={form.value}
            onChange={(e) => onChange({ value: e.target.value })}
            placeholder="rented"
          />
        </>
      ) : null}

      {kind === "create_activity" ? (
        <>
          <Select
            label="Activity type"
            required
            value={String(form.activity_type_id || "")}
            onChange={(e) => onChange({ activity_type_id: Number(e.target.value) })}
            options={activityTypes.map((t) => ({
              value: String(t.id),
              label: t.name,
            }))}
            placeholder={activityTypes.length ? undefined : "No activity types on this database"}
            hint="Uses mail.activity on the matching record."
          />
          <Input
            label="Summary"
            required
            value={form.activity_summary}
            onChange={(e) => onChange({ activity_summary: e.target.value })}
          />
        </>
      ) : null}

      {kind === "create_record" ? (
        <>
          <Input
            label="Target model"
            required
            value={form.target_model}
            onChange={(e) => onChange({ target_model: e.target.value })}
            className="font-mono text-sm"
            placeholder="mail.activity"
          />
          <Textarea
            label="Field values"
            hint="One key=value per line."
            rows={5}
            value={form.field_values_text}
            onChange={(e) => onChange({ field_values_text: e.target.value })}
            className="font-mono text-xs"
            placeholder={"summary=Follow up\nnote=Hello"}
          />
        </>
      ) : null}

      {kind === "mail_post" ? (
        <>
          <Select
            label="Mail template"
            value={form.mail_template_id === "" ? "" : String(form.mail_template_id)}
            onChange={(e) =>
              onChange({
                mail_template_id: e.target.value ? Number(e.target.value) : "",
              })
            }
            options={[
              { value: "", label: "None — use subject and body" },
              ...mailTemplates.map((t) => ({
                value: String(t.id),
                label: `#${t.id} · ${t.name}${t.subject ? ` (${t.subject})` : ""}`,
              })),
            ]}
          />
          <Select
            label="Post method"
            value={form.mail_post_method}
            onChange={(e) =>
              onChange({
                mail_post_method: e.target.value as "email" | "comment" | "note",
              })
            }
            options={[
              { value: "email", label: "Email" },
              { value: "comment", label: "Comment" },
              { value: "note", label: "Note" },
            ]}
          />
          <Input
            label="Subject"
            value={form.mail_subject}
            onChange={(e) => onChange({ mail_subject: e.target.value })}
          />
          <Input
            label="Email to"
            value={form.mail_email_to}
            onChange={(e) => onChange({ mail_email_to: e.target.value })}
            placeholder="Optional if the template sets recipients"
          />
          <Textarea
            label="Body HTML"
            rows={5}
            value={form.mail_body_html}
            onChange={(e) => onChange({ mail_body_html: e.target.value })}
            className="font-mono text-xs"
          />
        </>
      ) : null}

      {kind === "webhook" ? (
        <>
          <Input
            label="Webhook URL"
            required
            type="url"
            value={form.webhook_url}
            onChange={(e) => onChange({ webhook_url: e.target.value })}
            className="font-mono text-sm"
            placeholder="https://example.com/hooks/odoo"
          />
          <Input
            label="Payload fields"
            value={form.webhook_field_names}
            onChange={(e) => onChange({ webhook_field_names: e.target.value })}
            className="font-mono text-sm"
            placeholder="name, email, phone"
            hint="Optional comma-separated technical names."
          />
        </>
      ) : null}

      {kind === "sms" ? (
        <>
          <Input
            label="SMS template id"
            type="number"
            min={0}
            value={form.sms_template_id === "" ? "" : form.sms_template_id}
            onChange={(e) =>
              onChange({
                sms_template_id: e.target.value ? Number(e.target.value) : "",
              })
            }
            hint="Leave empty to create from the body below."
          />
          <Textarea
            label="SMS body"
            rows={3}
            value={form.sms_body}
            onChange={(e) => onChange({ sms_body: e.target.value })}
            placeholder="Hello {{ object.name }}"
          />
          <Select
            label="SMS method"
            value={form.sms_method}
            onChange={(e) =>
              onChange({ sms_method: e.target.value as "sms" | "comment" | "note" })
            }
            options={[
              { value: "sms", label: "SMS" },
              { value: "comment", label: "Comment" },
              { value: "note", label: "Note" },
            ]}
          />
        </>
      ) : null}

      {kind === "followers" || kind === "remove_followers" ? (
        <>
          <Input
            label="Partner ids"
            value={form.partner_ids_text}
            onChange={(e) => onChange({ partner_ids_text: e.target.value })}
            className="font-mono text-sm"
            placeholder="3, 7, 12"
            hint="Optional comma-separated partner ids."
          />
          {kind === "followers" ? (
            <>
              <Select
                label="Followers type"
                value={form.followers_type}
                onChange={(e) =>
                  onChange({
                    followers_type: e.target.value as "specific" | "generic",
                  })
                }
                options={[
                  { value: "specific", label: "Specific partners" },
                  { value: "generic", label: "From a field on the record" },
                ]}
              />
              {form.followers_type === "generic" ? (
                <Input
                  label="Partner field"
                  required
                  value={form.followers_partner_field_name}
                  onChange={(e) =>
                    onChange({ followers_partner_field_name: e.target.value })
                  }
                  className="font-mono text-sm"
                  placeholder="user_id.partner_id"
                />
              ) : null}
            </>
          ) : null}
        </>
      ) : null}

      {kind === "python_module" || kind === "code_live" ? (
        <>
          {kind === "python_module" ? (
            <Input
              label="Module technical name"
              required
              value={form.module_technical_name}
              onChange={(e) => onChange({ module_technical_name: e.target.value })}
              className="font-mono text-sm"
              pattern="[a-z][a-z0-9_]*"
            />
          ) : null}
          <Textarea
            label="Python code"
            required
            rows={8}
            value={form.python_code}
            onChange={(e) => onChange({ python_code: e.target.value })}
            className="font-mono text-xs"
          />
        </>
      ) : null}

      {kind === "python_module" || ADVANCED_ACTION_KINDS.has(kind) ? null : (
        <Disclosure title="Need Python or a webhook instead?">
          <p className="text-sm text-muted">
            Switch the action above to Export Python module (sandbox, then promote) or an
            advanced kind. Live Python is never the default path.
          </p>
        </Disclosure>
      )}
    </div>
  );
}

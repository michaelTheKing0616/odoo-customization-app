"use client";

import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import styles from "./MailTemplatesPage.module.css";

export type MailTemplatesCreateFormValues = {
  name: string;
  model: string;
  subject: string;
  email_to: string;
};

type Props = {
  form: MailTemplatesCreateFormValues;
  busy?: boolean;
  canSubmit?: boolean;
  submitBlockedReason?: string | null;
  onChange: (next: MailTemplatesCreateFormValues) => void;
  onSubmit: (e: FormEvent) => void;
};

export function MailTemplatesCreateForm({
  form,
  busy,
  canSubmit = true,
  submitBlockedReason,
  onChange,
  onSubmit,
}: Props) {
  return (
    <section
      className={styles.composer}
      id="mail-templates-create-form"
      data-testid="mail-templates-create-form"
    >
      <form onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <h2 className={styles.composerTitle}>New mail template</h2>
          <p className={styles.composerHint}>
            Bind to a live model. Body placeholders come from fields_get — no free invent.
            Recipients stay expressions (never hard-coded).
          </p>
        </div>
        <Input
          label="Name"
          required
          value={form.name}
          onChange={(e) => onChange({ ...form, name: e.target.value })}
        />
        <Input
          label="Model"
          required
          value={form.model}
          className="font-mono"
          onChange={(e) => onChange({ ...form, model: e.target.value })}
        />
        <Input
          label="Subject"
          required
          value={form.subject}
          onChange={(e) => onChange({ ...form, subject: e.target.value })}
        />
        <Input
          label="Email to (expression)"
          value={form.email_to}
          className="font-mono"
          onChange={(e) => onChange({ ...form, email_to: e.target.value })}
        />
        <div className="sm:col-span-2 flex flex-wrap items-center gap-2 pt-1">
          <Button
            type="submit"
            variant="primary"
            size="sm"
            loading={busy}
            disabled={!canSubmit || busy}
          >
            Create template
          </Button>
          {!canSubmit && submitBlockedReason ? (
            <span className="text-xs text-muted">{submitBlockedReason}</span>
          ) : null}
        </div>
      </form>
    </section>
  );
}

"use client";

import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import type { ModelComposerForm } from "@/lib/builderForm";
import { slugifyTechnical } from "@/lib/builderForm";

type ModelComposerProps = {
  form: ModelComposerForm;
  onChange: (patch: Partial<ModelComposerForm>) => void;
  onSubmit: (e: FormEvent) => void;
  busy?: boolean;
};

export function ModelComposer({ form, onChange, onSubmit, busy }: ModelComposerProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="builder-model-form">
      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">New model</p>
          <h2 className="text-base font-semibold text-ink">Create an x_ model</h2>
          <p className="mt-1 text-sm text-muted">
            Creates <code className="font-mono text-xs">x_name</code> plus default list, form, and
            search views, and grants Internal User ACL.
          </p>
        </div>
        <Input
          label="Label"
          required
          value={form.name}
          onChange={(e) => {
            const name = e.target.value;
            onChange({ name, model: slugifyTechnical(name) });
          }}
          placeholder="Project ticket"
          hint="Shown as the model title in Odoo."
        />
        <Input
          label="Technical name"
          required
          value={form.model}
          onChange={(e) => onChange({ model: e.target.value })}
          className="font-mono"
          pattern="x_[a-z0-9_]+"
          hint="Must start with x_ and use lowercase letters, digits, and underscores."
        />
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={form.enable_mail_thread}
            onChange={(e) => onChange({ enable_mail_thread: e.target.checked })}
            data-testid="builder-mail-thread"
          />
          <span>
            <span className="font-medium text-ink">Chatter and activities</span>
            <span className="mt-0.5 block text-xs text-muted">
              Ensures mail is installed. Full chatter still needs a Python export with mail.thread
              mixins.
            </span>
          </span>
        </label>
        <Button type="submit" variant="primary" disabled={busy} data-testid="builder-create-model">
          {busy ? "Working…" : "Create model"}
        </Button>
      </Card>
    </form>
  );
}

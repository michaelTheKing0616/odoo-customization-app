"use client";

import type { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export type QwebViewsCreateFormValues = {
  name: string;
  key: string;
  model: string;
};

type Props = {
  form: QwebViewsCreateFormValues;
  busy?: boolean;
  canSubmit?: boolean;
  submitBlockedReason?: string | null;
  onChange: (next: QwebViewsCreateFormValues) => void;
  onSubmit: (e: FormEvent) => void | Promise<void>;
};

export function QwebViewsCreateForm({
  form,
  busy,
  canSubmit = true,
  submitBlockedReason,
  onChange,
  onSubmit,
}: Props) {
  return (
    <form
      id="qweb-views-create-form"
      onSubmit={onSubmit}
      className="rounded-[12px] border border-[color-mix(in_srgb,var(--ink,#1a1c21)_10%,transparent)] bg-[color-mix(in_srgb,var(--surface-raised,#fff)_92%,transparent)] p-4"
      data-testid="qweb-views-create"
    >
      <p className="text-[0.6875rem] font-medium uppercase tracking-[0.06em] text-muted">
        New QWeb view
      </p>
      <p className="mt-1 text-sm text-muted">
        Creates a primary type=qweb arch with grounded blocks and the shared unsafe gate. Prefer
        inherit when extending stock templates.
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <Input
          label="Name"
          value={form.name}
          onChange={(e) => onChange({ ...form, name: e.target.value })}
          required
          data-testid="qweb-create-name"
        />
        <Input
          label="Key (module.name)"
          value={form.key}
          onChange={(e) => onChange({ ...form, key: e.target.value })}
          required
          placeholder="x_mod.document"
          data-testid="qweb-create-key"
        />
        <Input
          label="Model (optional)"
          value={form.model}
          onChange={(e) => onChange({ ...form, model: e.target.value })}
          placeholder="res.partner"
          data-testid="qweb-create-model"
        />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          type="submit"
          disabled={busy || !canSubmit}
          data-testid="qweb-create-submit"
        >
          {busy ? "Creating…" : "Create QWeb view"}
        </Button>
        {submitBlockedReason ? (
          <span className="text-xs text-muted">{submitBlockedReason}</span>
        ) : null}
      </div>
    </form>
  );
}

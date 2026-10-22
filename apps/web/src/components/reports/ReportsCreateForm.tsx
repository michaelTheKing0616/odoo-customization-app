"use client";

import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import styles from "./ReportsPage.module.css";

export type ReportsCreateFormValues = {
  name: string;
  model: string;
  report_key: string;
  paperformat_id: string;
};

type PaperOption = { id: number; name: string };

type ReportsCreateFormProps = {
  form: ReportsCreateFormValues;
  papers: PaperOption[];
  busy?: boolean;
  canSubmit?: boolean;
  submitBlockedReason?: string | null;
  onChange: (next: ReportsCreateFormValues) => void;
  onSubmit: (e: FormEvent) => void;
};

/**
 * PDF-06 — Compact create strip (operate density, not a marketing card).
 */
export function ReportsCreateForm({
  form,
  papers,
  busy,
  canSubmit = true,
  submitBlockedReason,
  onChange,
  onSubmit,
}: ReportsCreateFormProps) {
  return (
    <section
      className={styles.composer}
      id="reports-create-form"
      data-testid="reports-create-form"
    >
      <form onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <h2 className={styles.composerTitle}>New printout</h2>
          <p className={styles.composerHint}>
            Bind a QWeb report to a real model. External layout stays on.
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
          label="Report key (QWeb)"
          required
          value={form.report_key}
          className="font-mono"
          onChange={(e) => onChange({ ...form, report_key: e.target.value })}
        />
        <Select
          label="Paper format"
          value={form.paperformat_id}
          onChange={(e) => onChange({ ...form, paperformat_id: e.target.value })}
          options={[
            { value: "", label: "— default —" },
            ...papers.map((p) => ({ value: String(p.id), label: p.name })),
          ]}
        />
        <div className="sm:col-span-2 pt-1">
          <Button
            type="submit"
            variant="secondary"
            size="sm"
            disabled={busy || !canSubmit}
            title={submitBlockedReason ?? undefined}
            data-testid="reports-new-printout"
          >
            New printout
          </Button>
        </div>
      </form>
    </section>
  );
}

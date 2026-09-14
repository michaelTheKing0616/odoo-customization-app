"use client";

import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import type { Connection } from "@/lib/api";
import type { O2mComposerForm } from "@/lib/builderForm";
import { connectionSupports, connectionUnsupportedReason } from "@/lib/capabilities";

type RelationalPairPanelProps = {
  form: O2mComposerForm;
  onChange: (patch: Partial<O2mComposerForm>) => void;
  onSubmit: (e: FormEvent) => void;
  connection: Connection | null;
  busy?: boolean;
};

export function RelationalPairPanel({
  form,
  onChange,
  onSubmit,
  connection,
  busy,
}: RelationalPairPanelProps) {
  const canInject = connectionSupports(connection, "view_inject_inherit");

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="builder-o2m-form">
      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">Relations</p>
          <h2 className="text-base font-semibold text-ink">Link one2many</h2>
          <p className="mt-1 text-sm text-muted">
            Creates a required many2one on the child (on delete restrict) and an one2many on the
            parent — for example Book → Loans.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Parent model"
            required
            value={form.parent_model}
            onChange={(e) => onChange({ parent_model: e.target.value })}
            className="font-mono"
            placeholder="x_lib_book"
          />
          <Input
            label="Child model"
            required
            value={form.child_model}
            onChange={(e) => onChange({ child_model: e.target.value })}
            className="font-mono"
            placeholder="x_lib_loan"
          />
          <Input
            label="Parent O2M name"
            required
            value={form.parent_o2m_name}
            onChange={(e) => onChange({ parent_o2m_name: e.target.value })}
            className="font-mono"
          />
          <Input
            label="Child M2O name"
            required
            value={form.child_m2o_name}
            onChange={(e) => onChange({ child_m2o_name: e.target.value })}
            className="font-mono"
          />
          <Input
            label="Parent O2M label"
            required
            value={form.parent_o2m_string}
            onChange={(e) => onChange({ parent_o2m_string: e.target.value })}
          />
          <Input
            label="Child M2O label"
            required
            value={form.child_m2o_string}
            onChange={(e) => onChange({ child_m2o_string: e.target.value })}
          />
        </div>
        <label
          className="flex items-start gap-2 text-sm"
          title={connectionUnsupportedReason(connection, "view_inject_inherit") ?? undefined}
        >
          <input
            type="checkbox"
            className="mt-1"
            checked={form.inject_into_views && canInject}
            disabled={!canInject}
            onChange={(e) => onChange({ inject_into_views: e.target.checked })}
          />
          <span>
            Inject O2M into parent form
            {!canInject ? (
              <span className="mt-0.5 block text-xs text-muted">
                {connectionUnsupportedReason(connection, "view_inject_inherit")}
              </span>
            ) : null}
          </span>
        </label>
        <Button type="submit" variant="primary" disabled={busy}>
          {busy ? "Working…" : "Create relational pair"}
        </Button>
      </Card>
    </form>
  );
}

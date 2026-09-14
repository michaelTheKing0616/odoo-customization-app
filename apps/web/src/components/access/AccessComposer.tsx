"use client";

import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { CrudPermitsControl } from "@/components/security/CrudPermitsControl";
import type { GroupRow } from "@/lib/api";
import { isGlobalAccess, type AccessComposerForm } from "@/lib/accessForm";

type AccessComposerProps = {
  model: string;
  form: AccessComposerForm;
  groups: GroupRow[];
  onChange: (patch: Partial<AccessComposerForm>) => void;
  onSubmit: (e: FormEvent) => void;
  busy?: boolean;
  canSubmit?: boolean;
  submitBlockedReason?: string | null;
};

export function AccessComposer({
  model,
  form,
  groups,
  onChange,
  onSubmit,
  busy,
  canSubmit = true,
  submitBlockedReason,
}: AccessComposerProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="access-composer">
      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            New access right
          </p>
          <h2 className="text-base font-semibold text-ink">Grant CRUD on {model}</h2>
          <p className="mt-1 text-sm text-muted">
            Creates an ir.model.access line. Prefer a named group over a global grant.
          </p>
        </div>
        {isGlobalAccess(form.group_id) ? (
          <Callout variant="warning" title="Global access line">
            Empty group applies to all users. Use only when you understand the blast radius.
          </Callout>
        ) : null}
        <Input
          label="Name"
          required
          value={form.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder={`${model} user`}
        />
        <Select
          label="Group"
          options={[
            { value: "", label: "All users" },
            ...groups.map((g) => ({
              value: String(g.id),
              label: g.full_name || g.name,
            })),
          ]}
          value={form.group_id}
          onChange={(e) => onChange({ group_id: e.target.value })}
          hint="Studio-style ACL is group-scoped. All users is the global line."
        />
        <div>
          <p className="mb-2 text-sm font-medium text-ink">Permissions</p>
          <CrudPermitsControl value={form} onChange={onChange} />
        </div>
        <Button
          type="submit"
          variant="primary"
          disabled={busy || !canSubmit || !form.name.trim()}
          title={submitBlockedReason ?? undefined}
          loading={busy}
          data-testid="access-create"
        >
          Create access
        </Button>
      </Card>
    </form>
  );
}

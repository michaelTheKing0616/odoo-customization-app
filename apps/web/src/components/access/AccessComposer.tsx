"use client";

import Link from "next/link";
import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ExternalLink } from "@/components/ui/icons";
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
  /** Production R3: link to the plan card instead of an inline save. */
  planHref?: string | null;
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
  planHref,
}: AccessComposerProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="access-composer">
      <div className="ax-panel">
        <div>
          <h2 className="ax-panel-title">New access line on {model}</h2>
          <p className="ax-panel-sub">
            Pick a group and the operations it may run. Prefer a named group over a global line.
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
          hint="All users makes a global line that every user inherits."
        />
        <div>
          <p className="mb-2 text-sm font-medium text-ink">Permissions</p>
          <CrudPermitsControl value={form} onChange={onChange} />
        </div>
        <div className="ax-panel-actions">
          {planHref ? (
            <Button variant="primary" asChild>
              <Link href={planHref} data-testid="access-create-plan-link">
                Open plan card
                <ExternalLink className="h-3.5 w-3.5" aria-hidden />
              </Link>
            </Button>
          ) : (
            <Button
              type="submit"
              variant="primary"
              disabled={busy || !canSubmit || !form.name.trim()}
              title={submitBlockedReason ?? undefined}
              loading={busy}
              data-testid="access-create"
            >
              Save right
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}

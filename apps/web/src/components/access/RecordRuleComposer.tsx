"use client";

import { FormEvent } from "react";
import { DomainBuilder } from "@/components/DomainBuilder";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { GroupPicker } from "@/components/security/GroupPicker";
import { CrudPermitsControl } from "@/components/security/CrudPermitsControl";
import type { GroupRow } from "@/lib/api";
import { isGlobalRule, type RuleComposerForm } from "@/lib/accessForm";

type RecordRuleComposerProps = {
  model: string;
  form: RuleComposerForm;
  groups: GroupRow[];
  onChange: (patch: Partial<RuleComposerForm>) => void;
  onSubmit: (e: FormEvent) => void;
  busy?: boolean;
  canSubmit?: boolean;
  submitBlockedReason?: string | null;
};

export function RecordRuleComposer({
  model,
  form,
  groups,
  onChange,
  onSubmit,
  busy,
  canSubmit = true,
  submitBlockedReason,
}: RecordRuleComposerProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="access-rule-composer">
      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            New record rule
          </p>
          <h2 className="text-base font-semibold text-ink">Filter rows on {model}</h2>
          <p className="mt-1 text-sm text-muted">
            Domain uses the same builder as Automations. Empty groups create a global rule.
          </p>
        </div>
        {isGlobalRule(form.group_ids) ? (
          <Callout variant="danger" title="Global record rule">
            Empty groups create a global rule. That affects every user on this model.
          </Callout>
        ) : null}
        <Input
          label="Name"
          required
          value={form.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder={`${model} own records`}
        />
        <DomainBuilder
          label="Domain"
          hint="Leave [] to match every record the ACL already allows."
          value={form.domain_force}
          onChange={(domain_force) => onChange({ domain_force })}
        />
        <GroupPicker
          groups={groups}
          value={form.group_ids}
          onChange={(group_ids) => onChange({ group_ids })}
          label="Applies to groups"
          hint="Empty is global. Prefer a named group."
          noneLabel="Global — all users"
        />
        <div>
          <p className="mb-2 text-sm font-medium text-ink">Permissions this rule covers</p>
          <CrudPermitsControl value={form} onChange={onChange} />
        </div>
        <Button
          type="submit"
          variant="primary"
          disabled={busy || !canSubmit || !form.name.trim()}
          title={submitBlockedReason ?? undefined}
          loading={busy}
          data-testid="access-create-rule"
        >
          Create rule
        </Button>
      </Card>
    </form>
  );
}

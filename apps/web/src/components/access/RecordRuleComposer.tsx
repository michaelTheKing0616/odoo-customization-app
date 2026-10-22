"use client";

import Link from "next/link";
import { FormEvent } from "react";
import { DomainBuilder } from "@/components/DomainBuilder";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ExternalLink } from "@/components/ui/icons";
import { Input } from "@/components/ui/Input";
import { GroupPicker } from "@/components/security/GroupPicker";
import { CrudPermitsControl } from "@/components/security/CrudPermitsControl";
import type { GroupRow } from "@/lib/api";
import { isGlobalRule, type RuleComposerForm } from "@/lib/accessForm";
import { Term } from "@/components/ui/Term";

type RecordRuleComposerProps = {
  model: string;
  form: RuleComposerForm;
  groups: GroupRow[];
  onChange: (patch: Partial<RuleComposerForm>) => void;
  onSubmit: (e: FormEvent) => void;
  busy?: boolean;
  canSubmit?: boolean;
  submitBlockedReason?: string | null;
  planHref?: string | null;
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
  planHref,
}: RecordRuleComposerProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="access-rule-composer">
      <div className="ax-panel">
        <div>
          <h2 className="ax-panel-title">New <Term tech="ir.rule">record rule</Term> on {model}</h2>
          <p className="ax-panel-sub">
            A domain limits which rows the chosen groups see. No group makes the rule global.
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
          hint="Empty is global. Use a named group when you can."
          noneLabel="Global, all users"
        />
        <div>
          <p className="mb-2 text-sm font-medium text-ink">Permissions this rule covers</p>
          <CrudPermitsControl value={form} onChange={onChange} />
        </div>
        <div className="ax-panel-actions">
          {planHref ? (
            <Button variant="primary" asChild>
              <Link href={planHref} data-testid="access-create-rule-plan-link">
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
              data-testid="access-create-rule"
            >
              Save rule
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}

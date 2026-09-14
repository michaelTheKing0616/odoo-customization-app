"use client";

import { useState } from "react";
import Link from "next/link";
import { DomainBuilder } from "@/components/DomainBuilder";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { GroupPicker } from "@/components/security/GroupPicker";
import { CrudPermitsControl } from "@/components/security/CrudPermitsControl";
import { IconMenus, IconModels, IconViews } from "@/components/ui/icons";
import type { GroupRow, RecordRuleRow } from "@/lib/api";
import {
  builderHref,
  designerHref,
  isComposerDirty,
  isGlobalRule,
  menusHref,
  ruleFormFromRow,
} from "@/lib/accessForm";

type RecordRuleDetailProps = {
  connectionId: string;
  row: RecordRuleRow;
  groups: GroupRow[];
  busy?: boolean;
  canMutate?: boolean;
  canDelete?: boolean;
  mutateBlocked?: string | null;
  deleteBlocked?: string | null;
  onSave: (patch: {
    name: string;
    domain_force: string;
    group_ids: number[];
    perm_read: boolean;
    perm_write: boolean;
    perm_create: boolean;
    perm_unlink: boolean;
  }) => void;
  onDelete: () => void;
};

export function RecordRuleDetail({
  connectionId,
  row,
  groups,
  busy,
  canMutate = true,
  canDelete = true,
  mutateBlocked,
  deleteBlocked,
  onSave,
  onDelete,
}: RecordRuleDetailProps) {
  const [form, setForm] = useState(() => ruleFormFromRow(row));
  const dirty = isComposerDirty(form, ruleFormFromRow(row));
  const global = isGlobalRule(form.group_ids);

  return (
    <div className="space-y-4" data-testid="access-rule-detail">
      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
              Existing record rule
            </p>
            <h2 className="text-base font-semibold text-ink">{row.name}</h2>
            <p className="mt-0.5 font-mono text-[11px] text-muted">
              #{row.id} · {row.model}
            </p>
          </div>
          <Badge variant={global ? "warning" : "default"}>{global ? "Global" : "Grouped"}</Badge>
        </div>
        {global ? (
          <Callout variant="danger" title="Global record rule">
            Empty groups create a global rule. That affects every user on this model.
          </Callout>
        ) : null}
        <Input
          label="Name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <DomainBuilder
          label="Domain"
          hint="Saved on this rule. Snapshot is taken on save."
          value={form.domain_force}
          onChange={(domain_force) => setForm({ ...form, domain_force })}
        />
        <GroupPicker
          groups={groups}
          value={form.group_ids}
          onChange={(group_ids) => setForm({ ...form, group_ids })}
          label="Applies to groups"
          noneLabel="Global — all users"
        />
        <CrudPermitsControl
          value={form}
          onChange={(patch) => setForm({ ...form, ...patch })}
          disabled={!canMutate}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={busy || !dirty || !form.name.trim() || !canMutate}
            title={mutateBlocked ?? undefined}
            onClick={() =>
              onSave({
                name: form.name.trim(),
                domain_force: form.domain_force,
                group_ids: form.group_ids,
                perm_read: form.perm_read,
                perm_write: form.perm_write,
                perm_create: form.perm_create,
                perm_unlink: form.perm_unlink,
              })
            }
            data-testid="access-rule-save"
          >
            Save rule
          </Button>
          <Button type="button" variant="secondary" size="sm" asChild>
            <Link href={designerHref(connectionId, row.model)}>
              <IconViews className="h-3.5 w-3.5" aria-hidden />
              View Designer
            </Link>
          </Button>
          <Button type="button" variant="secondary" size="sm" asChild>
            <Link href={builderHref(connectionId, row.model)}>
              <IconModels className="h-3.5 w-3.5" aria-hidden />
              Models and fields
            </Link>
          </Button>
          <Button type="button" variant="secondary" size="sm" asChild>
            <Link href={menusHref(connectionId, row.model)}>
              <IconMenus className="h-3.5 w-3.5" aria-hidden />
              Menus
            </Link>
          </Button>
        </div>
      </Card>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy || !canDelete}
        title={deleteBlocked ?? undefined}
        className="text-danger"
        onClick={onDelete}
        data-testid="access-rule-delete"
      >
        Delete rule
      </Button>
    </div>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { CrudPermitsControl } from "@/components/security/CrudPermitsControl";
import { ExternalLink, IconMenus, IconModels, IconViews } from "@/components/ui/icons";
import { AccessCrudLetters } from "@/components/access/AccessCrudLetters";
import type { AccessRightRow, GroupRow } from "@/lib/api";
import {
  accessFormFromRow,
  builderHref,
  designerHref,
  isComposerDirty,
  isGlobalAccess,
  menusHref,
} from "@/lib/accessForm";

type AccessDetailProps = {
  connectionId: string;
  row: AccessRightRow;
  groups: GroupRow[];
  busy?: boolean;
  canMutate?: boolean;
  canDelete?: boolean;
  mutateBlocked?: string | null;
  deleteBlocked?: string | null;
  onSave: (patch: {
    name: string;
    group_id: number | null;
    clear_group: boolean;
    perm_read: boolean;
    perm_write: boolean;
    perm_create: boolean;
    perm_unlink: boolean;
  }) => void;
  onDelete: () => void;
  /** Production R3: link to the plan card instead of an inline save. */
  planHref?: string | null;
};

export function AccessDetail({
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
  planHref,
}: AccessDetailProps) {
  const [form, setForm] = useState(() => accessFormFromRow(row));
  const dirty = isComposerDirty(form, accessFormFromRow(row));

  return (
    <div className="space-y-4" data-testid="access-detail">
      <div className="ax-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="ax-panel-title">{row.name}</h2>
            <p className="ax-panel-id">
              #{row.id} · {row.model}
            </p>
          </div>
          <AccessCrudLetters value={row} testId="access-detail-crud" />
        </div>
        {isGlobalAccess(form.group_id) ? (
          <Callout variant="warning" title="Global access line">
            Empty group applies to all users.
          </Callout>
        ) : null}
        <Input
          label="Name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
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
          onChange={(e) => setForm({ ...form, group_id: e.target.value })}
        />
        <CrudPermitsControl
          value={form}
          onChange={(patch) => setForm({ ...form, ...patch })}
          disabled={!canMutate}
        />
        <div className="ax-panel-actions">
          {planHref ? (
            <Button variant="primary" size="sm" asChild>
              <Link href={planHref} data-testid="access-detail-plan-link">
                Open plan card
                <ExternalLink className="h-3.5 w-3.5" aria-hidden />
              </Link>
            </Button>
          ) : (
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={busy || !dirty || !form.name.trim() || !canMutate}
              title={mutateBlocked ?? undefined}
              onClick={() =>
                onSave({
                  name: form.name.trim(),
                  group_id: form.group_id ? Number(form.group_id) : null,
                  clear_group: !form.group_id,
                  perm_read: form.perm_read,
                  perm_write: form.perm_write,
                  perm_create: form.perm_create,
                  perm_unlink: form.perm_unlink,
                })
              }
              data-testid="access-detail-save"
            >
              Save right
            </Button>
          )}
          <Button type="button" variant="ghost" size="sm" asChild>
            <Link href={designerHref(connectionId, row.model)}>
              <IconViews className="h-3.5 w-3.5" aria-hidden />
              View Designer
            </Link>
          </Button>
          <Button type="button" variant="ghost" size="sm" asChild>
            <Link href={builderHref(connectionId, row.model)}>
              <IconModels className="h-3.5 w-3.5" aria-hidden />
              Models and fields
            </Link>
          </Button>
          <Button type="button" variant="ghost" size="sm" asChild>
            <Link href={menusHref(connectionId, row.model)}>
              <IconMenus className="h-3.5 w-3.5" aria-hidden />
              Menus
            </Link>
          </Button>
        </div>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy || !canDelete}
        title={deleteBlocked ?? undefined}
        className="text-danger"
        onClick={onDelete}
        data-testid="access-detail-delete"
      >
        Delete access
      </Button>
    </div>
  );
}

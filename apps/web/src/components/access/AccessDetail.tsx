"use client";

import { useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { CrudPermitsControl } from "@/components/security/CrudPermitsControl";
import { IconMenus, IconModels, IconViews } from "@/components/ui/icons";
import type { AccessRightRow, GroupRow } from "@/lib/api";
import {
  accessFormFromRow,
  builderHref,
  crudLetters,
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
}: AccessDetailProps) {
  const [form, setForm] = useState(() => accessFormFromRow(row));
  const dirty = isComposerDirty(form, accessFormFromRow(row));

  return (
    <div className="space-y-4" data-testid="access-detail">
      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
              Existing access line
            </p>
            <h2 className="text-base font-semibold text-ink">{row.name}</h2>
            <p className="mt-0.5 font-mono text-[11px] text-muted">
              #{row.id} · {row.model}
            </p>
          </div>
          <Badge variant={row.group_id ? "default" : "warning"}>{crudLetters(row)}</Badge>
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
            Save access
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
        data-testid="access-detail-delete"
      >
        Delete access
      </Button>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useState } from "react";
import { DomainBuilder } from "@/components/DomainBuilder";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import type { AutomationRow } from "@/lib/api";
import { designerHref, triggerLabel } from "@/lib/automationForm";

type AutomationDetailProps = {
  connectionId: string;
  row: AutomationRow;
  busy?: boolean;
  onSave: (patch: { name: string; filter_domain: string | null }) => void;
  onDuplicate: () => void;
  onToggleActive: () => void;
  onDelete: () => void;
};

export function AutomationDetail({
  connectionId,
  row,
  busy,
  onSave,
  onDuplicate,
  onToggleActive,
  onDelete,
}: AutomationDetailProps) {
  const [name, setName] = useState(row.name);
  const [filterDomain, setFilterDomain] = useState(row.filter_domain || "");
  const dirty =
    name.trim() !== row.name || (filterDomain || "") !== (row.filter_domain || "");

  return (
    <div className="space-y-4" data-testid="automations-detail">
      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
              Existing rule
            </p>
            <h2 className="text-base font-semibold text-ink">#{row.id}</h2>
          </div>
          <Badge variant={row.active ? "success" : "default"}>
            {row.active ? "Active" : "Inactive"}
          </Badge>
        </div>
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <div className="rounded-md border border-border-subtle bg-surface-muted/40 px-3 py-2">
          <p className="text-xs font-medium text-muted">Model</p>
          <p className="mt-1 font-mono text-sm text-ink">{row.model}</p>
          <p className="mt-2 text-xs text-muted">{triggerLabel(row.trigger)}</p>
        </div>
        <DomainBuilder
          label="Apply on"
          hint="Saved on this automation. Trigger and action stay as published — duplicate into a new rule to change those."
          value={filterDomain || "[]"}
          onChange={(next) => setFilterDomain(next === "[]" ? "" : next)}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={busy || !dirty || !name.trim()}
            onClick={() => onSave({ name: name.trim(), filter_domain: filterDomain || null })}
            data-testid="automations-detail-save"
          >
            Save name and domain
          </Button>
          <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={onDuplicate}>
            Start from this rule
          </Button>
          <Button type="button" variant="secondary" size="sm" asChild>
            <Link
              href={designerHref(connectionId, row.model)}
              data-testid="automations-detail-designer"
            >
              Open in View Designer
            </Link>
          </Button>
        </div>
      </Card>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={onToggleActive}>
          {row.active ? "Deactivate" : "Activate"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={busy}
          className="text-danger"
          onClick={onDelete}
        >
          Delete
        </Button>
      </div>
    </div>
  );
}

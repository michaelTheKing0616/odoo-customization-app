"use client";

import { Term } from "@/components/ui/Term";
import Link from "next/link";
import { useState } from "react";
import { DomainBuilder } from "@/components/DomainBuilder";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
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
    <div className="space-y-3" data-testid="automations-detail">
      <section className="au-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="au-panel-title">Rule #{row.id}</h2>
            <p className="au-panel-sub">
              Edit name and apply-on. Trigger and action stay as published. Duplicate into a
              new rule to change those.
            </p>
          </div>
          <Badge variant={row.active ? "success" : "default"}>
            {row.active ? "Active" : "Inactive"}
          </Badge>
        </div>
        <div className="au-panel-body">
          <Input
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div className="rounded-md border border-border-subtle bg-surface-muted/40 px-3 py-2">
            <p className="text-ui-meta text-muted">Model</p>
            <p className="mt-1 font-mono text-ui-body text-ink"><Term tech={row.model}>{row.model}</Term></p>
            <p className="mt-2 text-ui-meta text-muted">{triggerLabel(row.trigger)}</p>
          </div>
          <DomainBuilder
            label="Apply on"
            hint="Saved on this automation. Trigger and action stay as published."
            value={filterDomain || "[]"}
            onChange={(next) => setFilterDomain(next === "[]" ? "" : next)}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={busy || !dirty || !name.trim()}
              onClick={() =>
                onSave({ name: name.trim(), filter_domain: filterDomain || null })
              }
              data-testid="automations-detail-save"
            >
              Save
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={onDuplicate}
            >
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
        </div>
      </section>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={busy}
          onClick={onToggleActive}
        >
          {row.active ? "Deactivate" : "Activate"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={busy}
          className="text-danger"
          onClick={onDelete}
          data-testid="automations-detail-delete"
        >
          Delete
        </Button>
      </div>
    </div>
  );
}

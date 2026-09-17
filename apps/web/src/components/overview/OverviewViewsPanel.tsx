"use client";

import { useMemo, useState } from "react";
import type { ViewRow } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Disclosure } from "@/components/ui/Disclosure";
import { cn } from "@/lib/cn";

type Props = {
  model: string;
  views: ViewRow[];
};

type ViewGroupKey = "form" | "list" | "kanban" | "search" | "other";

const GROUP_ORDER: ViewGroupKey[] = ["form", "list", "kanban", "search", "other"];

const GROUP_LABEL: Record<ViewGroupKey, string> = {
  form: "Forms",
  list: "Lists",
  kanban: "Kanban",
  search: "Search",
  other: "Other",
};

function groupKey(type: string): ViewGroupKey {
  const t = type.toLowerCase();
  if (t === "form") return "form";
  if (t === "list" || t === "tree") return "list";
  if (t === "kanban") return "kanban";
  if (t === "search") return "search";
  return "other";
}

function ViewArchRow({ view }: { view: ViewRow }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="rounded-md border border-border-subtle bg-surface-raised"
      data-testid="overview-view-row"
      data-view-id={view.id}
    >
      <button
        type="button"
        className="flex w-full flex-wrap items-center gap-2 px-3 py-2 text-left"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{view.name}</span>
        <Badge variant="info">{view.type}</Badge>
        {view.priority != null ? (
          <span className="text-xs text-muted">priority {view.priority}</span>
        ) : null}
        <span
          className="font-mono text-xs text-muted"
          title="Odoo ir.ui.view database id (not a sequence index)"
        >
          id {view.id}
        </span>
        <span className={cn("text-xs text-muted", open && "text-ink")}>
          {open ? "Hide arch" : "Show arch"}
        </span>
      </button>
      {open ? (
        <div className="border-t border-border-subtle px-3 py-3">
          <CodeBlock language="xml" code={view.arch ?? "(no arch)"} />
        </div>
      ) : null}
    </div>
  );
}

export function OverviewViewsPanel({ model, views }: Props) {
  const grouped = useMemo(() => {
    const map = new Map<ViewGroupKey, ViewRow[]>();
    for (const key of GROUP_ORDER) map.set(key, []);
    for (const view of views) {
      map.get(groupKey(view.type))!.push(view);
    }
    return GROUP_ORDER.map((key) => ({
      key,
      label: GROUP_LABEL[key],
      rows: map.get(key) ?? [],
    })).filter((g) => g.rows.length > 0);
  }, [views]);

  if (views.length === 0) {
    return <p className="mt-6 text-sm text-muted">No views for this model.</p>;
  }

  return (
    <div className="mt-6 space-y-3" data-testid="overview-views-panel">
      <p className="text-sm text-muted" data-testid="overview-views-helper">
        Showing {views.length} view{views.length === 1 ? "" : "s"} for{" "}
        <span className="font-mono text-ink">{model}</span>. #ids are Odoo&apos;s database
        ids — gaps are normal.
      </p>
      {grouped.map((group) => (
        <Disclosure
          key={group.key}
          title={`${group.label} (${group.rows.length})`}
          defaultOpen={group.key === "form" || grouped.length === 1}
          testId={`overview-views-group-${group.key}`}
        >
          <ul className="space-y-2">
            {group.rows.map((view) => (
              <li key={view.id}>
                <ViewArchRow view={view} />
              </li>
            ))}
          </ul>
        </Disclosure>
      ))}
    </div>
  );
}

"use client";

import { useState } from "react";
import type { ProjectDiffOut } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { DiffView } from "@/components/ui/DiffView";
import { Tabs } from "@/components/ui/Tabs";
import {
  PROJECT_DIFF_FILTERS,
  projectDiffHeadline,
  projectDiffStats,
  type ProjectDiffFilter,
} from "@/lib/projects-journey";

type ProjectDiffPanelProps = {
  diff: ProjectDiffOut;
};

export function ProjectDiffPanel({ diff }: ProjectDiffPanelProps) {
  const [filter, setFilter] = useState<ProjectDiffFilter>("all");
  const stats = projectDiffStats(diff);
  const specModels = [...diff.to_create_models, ...diff.existing_models].join("\n");
  const liveModels = diff.existing_models.join("\n");
  const showConflicts = filter === "all" || filter === "conflicts";
  const showCreate = filter === "all" || filter === "create";
  const showExisting = filter === "all" || filter === "existing";
  const sliceEmpty =
    (filter === "conflicts" && stats.conflicts === 0) ||
    (filter === "create" && stats.toCreate === 0) ||
    (filter === "existing" && stats.alreadyLive === 0);

  return (
    <Card className="p-5" data-testid="project-diff-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Review vs live
          </p>
          <h2 className="text-base font-semibold text-ink">Change review</h2>
          <p className="mt-1 text-sm text-muted" data-testid="project-diff-headline">
            {projectDiffHeadline(diff)}
          </p>
        </div>
        <div className="flex flex-wrap gap-1" data-testid="project-diff-filters">
          {PROJECT_DIFF_FILTERS.map((row) => (
            <Button
              key={row.id}
              type="button"
              size="sm"
              variant={filter === row.id ? "secondary" : "ghost"}
              onClick={() => setFilter(row.id)}
            >
              {row.label}
            </Button>
          ))}
        </div>
      </div>

      <dl className="project-diff-stats mt-4" data-testid="project-diff-stats">
        <div>
          <dt>To create</dt>
          <dd>{stats.toCreate}</dd>
        </div>
        <div>
          <dt>Already live</dt>
          <dd>{stats.alreadyLive}</dd>
        </div>
        <div>
          <dt>Conflicts</dt>
          <dd className={stats.conflicts > 0 ? "text-danger" : undefined}>{stats.conflicts}</dd>
        </div>
      </dl>

      <p className="mt-3 text-xs text-muted">
        This diff is models and fields only. Views, menus, and ACL stay in ModuleSpec Generate UI.
        Promote stays human.
      </p>

      <Tabs
        className="mt-4"
        items={[
          {
            value: "summary",
            label: "Summary",
            content: (
              <div className="space-y-4 text-sm" data-testid="project-diff-summary">
                {sliceEmpty ? (
                  <p className="text-muted">Nothing in this slice.</p>
                ) : null}
                {showConflicts && diff.conflicts.length > 0 ? (
                  <div>
                    <Badge variant="danger">Conflicts</Badge>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-danger">
                      {diff.conflicts.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {showCreate && diff.to_create_models.length > 0 ? (
                  <div>
                    <Badge variant="info">Models to create</Badge>
                    <ul className="mt-2 list-disc space-y-1 pl-5 font-mono text-accent">
                      {diff.to_create_models.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {showCreate && diff.to_create_fields.length > 0 ? (
                  <div>
                    <Badge variant="info">Fields to create</Badge>
                    <ul className="mt-2 list-disc space-y-1 pl-5 font-mono text-accent">
                      {diff.to_create_fields.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {showExisting && diff.existing_models.length > 0 ? (
                  <div>
                    <Badge variant="default">Models already live</Badge>
                    <p className="mt-2 font-mono text-xs text-muted">
                      {diff.existing_models.join(", ")}
                    </p>
                  </div>
                ) : null}
                {showExisting && diff.existing_fields.length > 0 ? (
                  <div>
                    <Badge variant="default">Fields already live</Badge>
                    <p className="mt-2 font-mono text-xs text-muted">
                      {diff.existing_fields.join(", ")}
                    </p>
                  </div>
                ) : null}
                {filter === "all" && stats.toCreate === 0 && stats.conflicts === 0 ? (
                  <p className="text-muted">
                    No creates and no conflicts. Apply would skip existing models and fields.
                  </p>
                ) : null}
              </div>
            ),
          },
          {
            value: "models",
            label: "Models",
            content: (
              <div className="space-y-2">
                <p className="text-xs text-muted">Live models vs draft models (creates plus already live).</p>
                <DiffView
                  before={liveModels || "(none on live)"}
                  after={specModels || "(none in draft)"}
                />
              </div>
            ),
          },
          {
            value: "fields",
            label: "Fields",
            content: (
              <div className="space-y-2">
                <p className="text-xs text-muted">Already-live fields vs fields this draft would create.</p>
                <DiffView
                  before={diff.existing_fields.join("\n") || "(none on live)"}
                  after={diff.to_create_fields.join("\n") || "(none to create)"}
                />
              </div>
            ),
          },
        ]}
      />
    </Card>
  );
}

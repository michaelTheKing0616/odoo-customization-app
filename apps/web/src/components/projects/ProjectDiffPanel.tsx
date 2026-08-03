"use client";

import { useState } from "react";
import type { ProjectDiffOut } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { DiffView } from "@/components/ui/DiffView";
import { Tabs } from "@/components/ui/Tabs";

type Filter = "all" | "conflicts" | "create" | "existing";

type Props = {
  diff: ProjectDiffOut;
};

export function ProjectDiffPanel({ diff }: Props) {
  const [filter, setFilter] = useState<Filter>("all");

  const specModels = [
    ...diff.to_create_models,
    ...diff.existing_models,
  ].join("\n");
  const liveModels = diff.existing_models.join("\n");

  const showConflicts = filter === "all" || filter === "conflicts";
  const showCreate = filter === "all" || filter === "create";
  const showExisting = filter === "all" || filter === "existing";

  return (
    <Card className="p-4" data-testid="project-diff-panel">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium text-ink">{diff.message || "Diff vs live"}</p>
        <div className="ml-auto flex gap-2">
          {(["all", "conflicts", "create", "existing"] as const).map((f) => (
            <Button
              key={f}
              type="button"
              size="sm"
              variant={filter === f ? "secondary" : "ghost"}
              onClick={() => setFilter(f)}
            >
              {f}
            </Button>
          ))}
        </div>
      </div>

      <Tabs
        className="mt-4"
        items={[
          {
            value: "summary",
            label: "Summary",
            content: (
              <div className="space-y-3 text-sm">
                {showConflicts && diff.conflicts.length > 0 ? (
                  <div>
                    <Badge variant="danger">Conflicts</Badge>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-danger">
                      {diff.conflicts.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {showCreate && diff.to_create_models.length > 0 ? (
                  <div>
                    <Badge variant="info">Models to create</Badge>
                    <ul className="mt-2 list-disc space-y-1 pl-5 font-mono text-accent">
                      {diff.to_create_models.map((m) => (
                        <li key={m}>{m}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {showCreate && diff.to_create_fields.length > 0 ? (
                  <div>
                    <Badge variant="info">Fields to create</Badge>
                    <ul className="mt-2 list-disc space-y-1 pl-5 font-mono text-accent">
                      {diff.to_create_fields.map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {showExisting && diff.existing_models.length > 0 ? (
                  <p className="text-muted">
                    Existing models: {diff.existing_models.join(", ")}
                  </p>
                ) : null}
                {showExisting && diff.existing_fields.length > 0 ? (
                  <p className="text-muted">
                    Existing fields: {diff.existing_fields.join(", ")}
                  </p>
                ) : null}
              </div>
            ),
          },
          {
            value: "models",
            label: "Models diff",
            content: (
              <DiffView
                before={liveModels || "(none on live)"}
                after={specModels || "(none in draft)"}
              />
            ),
          },
          {
            value: "fields",
            label: "Fields diff",
            content: (
              <DiffView
                before={diff.existing_fields.join("\n") || "(none on live)"}
                after={diff.to_create_fields.join("\n") || "(none to create)"}
              />
            ),
          },
        ]}
      />
    </Card>
  );
}

"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { IconProjects } from "@/components/ui/icons";
import { EMPTY_STATES } from "@/lib/copy-guide";
import { cn } from "@/lib/cn";
import {
  filterProjectBoard,
  formatProjectWhen,
  projectSpecSummary,
  projectStatusLabel,
  projectTemplateLabel,
  sortProjectBoard,
  type ProjectRow,
  type ProjectsBoardFilter,
} from "@/lib/projects-journey";

const FILTERS: { id: ProjectsBoardFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "draft", label: "Draft" },
  { id: "applied", label: "Applied" },
  { id: "archived", label: "Archived" },
];

type ProjectBoardProps = {
  projects: ProjectRow[];
  loading?: boolean;
  selectedId: string | null;
  filter: ProjectsBoardFilter;
  query: string;
  onQueryChange: (query: string) => void;
  onFilterChange: (filter: ProjectsBoardFilter) => void;
  onSelect: (project: ProjectRow) => void;
  onCreate: () => void;
};

function statusVariant(label: string): "info" | "success" | "default" {
  if (label === "Applied") return "success";
  if (label === "Archived") return "default";
  return "info";
}

export function ProjectBoard({
  projects,
  loading,
  selectedId,
  filter,
  query,
  onQueryChange,
  onFilterChange,
  onSelect,
  onCreate,
}: ProjectBoardProps) {
  const sorted = sortProjectBoard(projects);
  const filtered = filterProjectBoard(sorted, filter).filter((row) => {
    const haystack = `${row.name} ${row.id} ${row.template_id ?? ""}`.toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });

  return (
    <div className="space-y-3" data-testid="projects-board">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Release board</h2>
        <Button type="button" variant="secondary" size="sm" onClick={onCreate} data-testid="projects-new">
          New draft
        </Button>
      </div>
      <input
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Filter by name or id"
        aria-label="Filter projects"
        data-testid="projects-board-filter"
        className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
      />
      <div className="flex flex-wrap gap-1" data-testid="projects-board-filters">
        {FILTERS.map((row) => (
          <Button
            key={row.id}
            type="button"
            size="sm"
            variant={filter === row.id ? "secondary" : "ghost"}
            onClick={() => onFilterChange(row.id)}
          >
            {row.label}
          </Button>
        ))}
      </div>
      {loading ? (
        <div className="space-y-2" data-testid="projects-board-loading">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<IconProjects className="h-5 w-5" />}
          title={projects.length === 0 ? "No drafts yet" : "No matching drafts"}
          description={
            projects.length === 0
              ? EMPTY_STATES.projects
              : "Try a different filter, or create a new draft."
          }
          action={
            <Button type="button" variant="primary" size="sm" onClick={onCreate}>
              Create draft
            </Button>
          }
        />
      ) : (
        <ul className="project-board-list" data-testid="projects-board-list">
          {filtered.map((project) => {
            const selected = selectedId === project.id;
            const status = projectStatusLabel(project);
            const summary = projectSpecSummary(project.spec_json);
            return (
              <li key={project.id}>
                <Card
                  role="button"
                  tabIndex={0}
                  aria-pressed={selected}
                  data-testid={`project-row-${project.id}`}
                  onClick={() => onSelect(project)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(project);
                    }
                  }}
                  className={cn(
                    "project-board-card cursor-pointer p-3 transition-colors hover:bg-surface-muted",
                    selected && "is-selected border-accent bg-accent-subtle",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink">{project.name}</p>
                      <p className="mt-0.5 font-mono text-[11px] text-muted">
                        {project.id.slice(0, 8)} · {projectTemplateLabel(project.template_id)}
                      </p>
                    </div>
                    <Badge variant={statusVariant(status)}>{status}</Badge>
                  </div>
                  <p className="mt-2 text-[11px] text-muted">
                    {summary.models} models · {summary.fields} fields · {formatProjectWhen(project.updated_at ?? project.created_at)}
                  </p>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

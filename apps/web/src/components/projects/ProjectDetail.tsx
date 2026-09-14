"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { SuggestTemplateButton } from "@/components/SuggestTemplateButton";
import { SaveAsComponentButton } from "@/components/SaveAsComponentButton";
import {
  designerHref,
  firstCustomModel,
  formatProjectWhen,
  hasProjectSpec,
  isComponentSpec,
  isProjectArchived,
  modulespecHref,
  projectSpecSummary,
  projectStatusLabel,
  projectTemplateLabel,
  type ProjectRow,
} from "@/lib/projects-journey";

type ProjectDetailProps = {
  connectionId: string;
  project: ProjectRow;
  applyBlocked?: string | null;
  busy?: boolean;
  onDelete: () => void;
  canDelete?: boolean;
  deleteBlocked?: string | null;
};

export function ProjectDetail({
  connectionId,
  project,
  applyBlocked,
  busy,
  onDelete,
  canDelete = true,
  deleteBlocked,
}: ProjectDetailProps) {
  const summary = projectSpecSummary(project.spec_json);
  const model = firstCustomModel(project.spec_json);
  const status = projectStatusLabel(project);
  const hasSpec = hasProjectSpec(project.spec_json);

  return (
    <div className="space-y-4" data-testid="projects-detail">
      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
              Selected draft
            </p>
            <h2 className="text-base font-semibold text-ink">{project.name}</h2>
            <p className="mt-0.5 font-mono text-[11px] text-muted">{project.id}</p>
          </div>
          <div className="flex flex-wrap gap-1">
            <Badge variant={status === "Applied" ? "success" : status === "Archived" ? "default" : "info"}>
              {status}
            </Badge>
            <Badge variant="default">{projectTemplateLabel(project.template_id)}</Badge>
          </div>
        </div>
        <dl className="project-packet-facts">
          <div>
            <dt>Models</dt>
            <dd>{summary.models}</dd>
          </div>
          <div>
            <dt>Fields</dt>
            <dd>{summary.fields}</dd>
          </div>
          <div>
            <dt>Views</dt>
            <dd>{summary.views}</dd>
          </div>
          <div>
            <dt>Menus</dt>
            <dd>{summary.menus}</dd>
          </div>
        </dl>
        <p className="text-xs text-muted" data-testid="projects-detail-updated">
          Updated {formatProjectWhen(project.updated_at ?? project.created_at)}. Apply writes models
          and fields. Views stay in ModuleSpec Generate UI.
        </p>
        {applyBlocked ? (
          <p className="text-xs text-warning" data-testid="projects-detail-blocked">
            {applyBlocked}
          </p>
        ) : null}
        {isProjectArchived(project) ? (
          <p className="text-xs text-muted">Un-archive this draft before Apply.</p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" size="sm" asChild>
            <Link href={modulespecHref(connectionId, project.id)} data-testid="projects-open-modulespec">
              Open ModuleSpec
            </Link>
          </Button>
          <Button type="button" variant="secondary" size="sm" asChild>
            <Link
              href={designerHref(connectionId, model)}
              data-testid="projects-open-designer"
              title={
                model
                  ? `Opens View Designer on ${model}. Apply first so the form exists on this connection.`
                  : "Opens View Designer. Apply first so views exist on this connection."
              }
            >
              View Designer
            </Link>
          </Button>
          {hasSpec ? (
            <SuggestTemplateButton
              spec={project.spec_json}
              connectionId={connectionId}
              projectId={project.id}
              disabled={busy}
            />
          ) : null}
          {isComponentSpec(project.spec_json) ? (
            <SaveAsComponentButton spec={project.spec_json} disabled={busy} />
          ) : null}
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
        data-testid="projects-detail-delete"
      >
        Delete draft
      </Button>
    </div>
  );
}

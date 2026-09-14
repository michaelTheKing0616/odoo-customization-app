"use client";

import type { ComponentProps } from "react";
import { Badge } from "@/components/ui/Badge";
import {
  projectsSessionHint,
  type ProjectsSessionState,
} from "@/lib/projects-journey";

const STATE_COPY: Record<
  ProjectsSessionState,
  { label: string; variant: ComponentProps<typeof Badge>["variant"] }
> = {
  archived: { label: "Archived", variant: "default" },
  applied: { label: "Applied", variant: "success" },
  draft: { label: "Draft", variant: "info" },
};

type ProjectSessionBarProps = {
  sessionState: ProjectsSessionState;
  submitLabel: string;
};

export function ProjectSessionBar({ sessionState, submitLabel }: ProjectSessionBarProps) {
  const copy = STATE_COPY[sessionState];
  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-2 shadow-subtle"
      data-testid="projects-session-bar"
    >
      <span data-testid="projects-session-state">
        <Badge variant={copy.variant}>{copy.label}</Badge>
      </span>
      <p className="mr-auto max-w-xl text-xs text-muted" data-testid="projects-session-hint">
        {projectsSessionHint(sessionState)}
      </p>
      <span className="text-xs text-muted" data-testid="projects-session-submit-hint">
        {submitLabel}
      </span>
    </div>
  );
}

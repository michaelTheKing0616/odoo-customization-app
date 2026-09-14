"use client";

import { useState } from "react";
import type { ProjectDiffOut, SnapshotRow } from "@/lib/api";
import { ProjectApplyBar } from "@/components/projects/ProjectApplyBar";
import { ProjectBoard } from "@/components/projects/ProjectBoard";
import { ProjectCreateCard } from "@/components/projects/ProjectCreateCard";
import { ProjectDetail } from "@/components/projects/ProjectDetail";
import { ProjectDiffPanel } from "@/components/projects/ProjectDiffPanel";
import { ProjectHandoffBar } from "@/components/projects/ProjectHandoffBar";
import { ProjectHistory } from "@/components/projects/ProjectHistory";
import { ProjectHonestyBanners } from "@/components/projects/ProjectHonestyBanners";
import { ProjectSessionBar } from "@/components/projects/ProjectSessionBar";
import { ProjectShell } from "@/components/projects/ProjectShell";
import {
  projectsHonestyGate,
  projectsJourneyFromState,
  projectsSessionState,
  sessionSubmitHint,
  type ProjectRow,
} from "@/lib/projects-journey";
import "@/styles/studio-refinement.css";

const SAMPLE: ProjectRow = {
  id: "e2e-visitor",
  name: "Visitor log",
  template_id: "library",
  status: "draft",
  lifecycle_status: "active",
  spec_json: {
    models: [
      {
        model: "x_visitor_log",
        fields: [
          { name: "x_name", ttype: "char" },
          { name: "x_host_id", ttype: "many2one" },
        ],
      },
    ],
    views: [{ name: "x_visitor_log.form" }],
    menus: [{ name: "Visitor log" }],
  },
  created_at: "2026-09-14T10:00:00Z",
  updated_at: "2026-09-14T12:00:00Z",
};

const APPLIED: ProjectRow = {
  ...SAMPLE,
  id: "e2e-applied",
  name: "Loans",
  status: "applied",
  template_id: null,
  spec_json: { models: [{ model: "x_lib_loan", fields: [{ name: "x_book_id" }] }] },
};

const DIFF: ProjectDiffOut = {
  ok: true,
  message: "Ready",
  to_create_models: ["x_visitor_log"],
  existing_models: ["res.partner"],
  to_create_fields: ["x_visitor_log.x_name", "x_visitor_log.x_host_id"],
  existing_fields: ["res.partner.name"],
  conflicts: [],
};

const SNAPSHOTS: SnapshotRow[] = [
  {
    id: "snap-e2e",
    resource_type: "model",
    resource_key: "model:x_visitor_log",
    label: "Before apply x_visitor_log",
    reversible: "partial",
    created_at: "2026-09-14T11:00:00Z",
  },
];

export default function ProjectsE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [selectedId, setSelectedId] = useState(SAMPLE.id);
  const selected = selectedId === SAMPLE.id ? SAMPLE : APPLIED;
  const journey = projectsJourneyFromState({
    selected: true,
    hasDiff: true,
    applied: selected.status === "applied",
  });
  const sessionState = projectsSessionState(selected);

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <ProjectShell connectionId="e2e-mock" connectionName="E2E mock" projectName={selected.name} journey={journey}>
      <ProjectHonestyBanners
        gate={projectsHonestyGate({ writeMode: "standard", localSandboxUrl: true })}
        slotNote="1 of 3 active — archive anytime to free a slot."
      />
      <ProjectSessionBar
        sessionState={sessionState}
        submitLabel={sessionSubmitHint({ sessionState, hasDiff: true, canApply: true })}
      />
      <div className="project-workbench">
        <ProjectBoard
          projects={[SAMPLE, APPLIED]}
          selectedId={selectedId}
          filter="all"
          query=""
          onQueryChange={() => undefined}
          onFilterChange={() => undefined}
          onSelect={(project) => setSelectedId(project.id)}
          onCreate={() => undefined}
        />
        <div className="space-y-4">
          {selectedId ? null : (
            <ProjectCreateCard
              name="Library draft"
              templateId="library"
              onNameChange={() => undefined}
              onTemplateChange={() => undefined}
              onSubmit={(event) => event.preventDefault()}
            />
          )}
          <ProjectDetail
            connectionId="e2e-mock"
            project={selected}
            onDelete={() => undefined}
          />
          <ProjectApplyBar
            project={selected}
            busy={null}
            canMutate
            canApply
            hasDiff
            onReview={() => undefined}
            onApply={() => undefined}
            onArchive={() => undefined}
          />
          <ProjectDiffPanel diff={DIFF} />
          <ProjectHistory
            connectionId="e2e-mock"
            project={selected}
            snapshots={SNAPSHOTS}
            onRollback={() => undefined}
          />
        </div>
      </div>
      <ProjectHandoffBar
        connectionId="e2e-mock"
        projectId={selected.id}
        designerModel="x_visitor_log"
      />
    </ProjectShell>
  );
}

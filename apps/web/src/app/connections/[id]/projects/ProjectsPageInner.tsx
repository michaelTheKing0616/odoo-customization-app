"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
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
  api,
  ConfirmationRequiredError,
  Connection,
  FeatureGatedError,
  ProjectDiffOut,
  SnapshotRow,
} from "@/lib/api";
import { isLocalSandboxUrl } from "@/lib/odoo-urls";
import { useEntitlements } from "@/lib/useEntitlements";
import { useUpgrade } from "@/lib/upgrade-context";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import {
  mutationAllowed,
  mutationBlockedReason,
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
} from "@/lib/capabilities";
import {
  applyRisks,
  applySnapshotNote,
  firstCustomModel,
  projectsErrorTitle,
  projectsHonestyGate,
  projectsJourneyFromState,
  projectsSessionState,
  sessionSubmitHint,
  type ProjectRow,
  type ProjectsBoardFilter,
  type ProjectsBusy,
} from "@/lib/projects-journey";

const CONFIRM_PHRASE = "I understand the risks";

export default function ProjectsPageInner() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [name, setName] = useState("Library draft");
  const [templateId, setTemplateId] = useState("library");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<ProjectsBusy>(null);
  const [listLoading, setListLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [applyTarget, setApplyTarget] = useState<ProjectRow | null>(null);
  const [confirmPhrase, setConfirmPhrase] = useState(CONFIRM_PHRASE);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState<ProjectsBoardFilter>("all");
  const [query, setQuery] = useState("");
  const [diffTargetId, setDiffTargetId] = useState<string | null>(null);
  const [diff, setDiff] = useState<ProjectDiffOut | null>(null);
  const [failed, setFailed] = useState(false);
  const { data: entitlements } = useEntitlements();
  const { openUpgrade } = useUpgrade();

  useSyncShellContext({
    draftSummary: projects.find((row) => row.id === selectedId)?.name,
  });

  const refresh = useCallback(async () => {
    const [conn, rows, snaps] = await Promise.all([
      api.getConnection(connectionId),
      api.listProjects(connectionId),
      api.listSnapshots(connectionId).catch(() => [] as SnapshotRow[]),
    ]);
    setConnection(conn);
    setProjects(rows);
    setSnapshots(snaps);
  }, [connectionId]);

  useEffect(() => {
    setListLoading(true);
    refresh()
      .catch((err: Error) => {
        setFailed(true);
        setError(err.message);
      })
      .finally(() => setListLoading(false));
  }, [refresh]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromQuery = new URLSearchParams(window.location.search).get("project");
    if (fromQuery) setSelectedId(fromQuery);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    url.searchParams.set("project", selectedId);
    window.history.replaceState(null, "", url.toString());
  }, [selectedId]);

  const selected = projects.find((row) => row.id === selectedId) ?? null;
  const selectedDiff = selected && diff && diffTargetId === selected.id ? diff : null;
  const canMutate = mutationAllowed(connection);
  const mutateBlocked = mutationBlockedReason(connection);
  const localSandbox = Boolean(connection?.url && isLocalSandboxUrl(connection.url));
  const gate = projectsHonestyGate({
    writeMode: connection?.write_mode,
    localSandboxUrl: localSandbox,
  });
  const sessionState = projectsSessionState(selected);
  const journey = projectsJourneyFromState({
    selected: Boolean(selected),
    hasDiff: Boolean(selectedDiff),
    applied: Boolean(selected && selected.status === "applied"),
    busy,
    failed,
  });

  function projectApplyAllowed(project: ProjectRow): boolean {
    const opts = scaffoldOptsFromSpec(project.spec_json);
    if (project.template_id === "library") {
      opts.requireObjectWrite = true;
    }
    return scaffoldApplyAllowed(connection, opts);
  }

  function projectApplyBlocked(project: ProjectRow): string | null {
    const opts = scaffoldOptsFromSpec(project.spec_json);
    if (project.template_id === "library") {
      opts.requireObjectWrite = true;
    }
    return scaffoldApplyBlockedReason(connection, opts);
  }

  function rememberSelection(projectId: string) {
    setSelectedId(projectId);
    setCreating(false);
    setNotice(null);
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setBusy("create");
    setError(null);
    setNotice(null);
    setFailed(false);
    try {
      const created = await api.createProject(connectionId, {
        name,
        template_id: templateId || null,
        spec_json: {},
      });
      setNotice(
        `Created draft ${created.name} (${created.id.slice(0, 8)}…) from ${
          created.template_id ?? "blank"
        }`,
      );
      setName("Library draft");
      await refresh();
      rememberSelection(created.id);
    } catch (err) {
      if (err instanceof FeatureGatedError) {
        openUpgrade(err.featureKey);
      }
      setFailed(true);
      setError(err instanceof Error ? err.message : "Create draft failed");
    } finally {
      setBusy(null);
    }
  }

  async function doApply(phrase: string) {
    if (!applyTarget) return;
    setBusy("apply");
    setError(null);
    setNotice(null);
    setFailed(false);
    try {
      const res = await api.applyProject(connectionId, applyTarget.id, {
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setNotice(
        res.message +
          (res.warnings.length ? ` · ${res.warnings.slice(0, 2).join("; ")}` : ""),
      );
      setConfirmOpen(false);
      setApplyTarget(null);
      setDiff(null);
      setDiffTargetId(null);
      await refresh();
      rememberSelection(applyTarget.id);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmPhrase(err.confirm_phrase || CONFIRM_PHRASE);
        setConfirmOpen(true);
        setError(err.warning || err.message);
      } else {
        setFailed(true);
        setError(err instanceof Error ? err.message : "Apply failed");
      }
    } finally {
      setBusy(null);
    }
  }

  async function onDiff(project: ProjectRow) {
    setBusy("diff");
    setError(null);
    setNotice(null);
    setFailed(false);
    try {
      const report = await api.projectDiff(connectionId, project.id);
      setDiffTargetId(project.id);
      setDiff(report);
      setNotice(report.message || "Review vs live is ready");
    } catch (err) {
      setDiff(null);
      setDiffTargetId(null);
      setFailed(true);
      setError(err instanceof Error ? err.message : "Review vs live failed");
    } finally {
      setBusy(null);
    }
  }

  async function onArchive(project: ProjectRow) {
    setBusy("archive");
    setError(null);
    try {
      if ((project.lifecycle_status ?? "active") === "archived") {
        await api.unarchiveProject(connectionId, project.id);
      } else {
        await api.archiveProject(connectionId, project.id);
      }
      await refresh();
    } catch (err) {
      if (err instanceof FeatureGatedError) openUpgrade(err.featureKey);
      setFailed(true);
      setError(err instanceof Error ? err.message : "Archive failed");
    } finally {
      setBusy(null);
    }
  }

  async function onDelete(project: ProjectRow) {
    setBusy("delete");
    setError(null);
    try {
      await api.deleteProject(connectionId, project.id);
      if (diffTargetId === project.id) {
        setDiff(null);
        setDiffTargetId(null);
      }
      if (selectedId === project.id) setSelectedId(null);
      await refresh();
    } catch (err) {
      setFailed(true);
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(null);
    }
  }

  async function onRollback(snapshotId: string) {
    setBusy("rollback");
    setError(null);
    setNotice(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshotId);
      setNotice(`Restored ${res.restored} #${res.id}`);
      await refresh();
    } catch (err) {
      setFailed(true);
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(null);
    }
  }

  const slotNote = useMemo(() => {
    if (entitlements?.active_project_limit == null) return null;
    return `${entitlements.active_projects} of ${entitlements.active_project_limit} active — archive anytime to free a slot; history stays readable. Un-archive whenever you have a free slot.`;
  }, [entitlements]);

  const showCreate = creating || !selected;

  return (
    <ProjectShell
      connectionId={connectionId}
      connectionName={connection?.name}
      projectName={selected?.name}
      journey={journey}
    >
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      <ProjectHonestyBanners gate={gate} mutateBlocked={mutateBlocked} slotNote={slotNote} />
      <ProjectSessionBar
        sessionState={sessionState}
        submitLabel={sessionSubmitHint({
          sessionState,
          hasDiff: Boolean(selectedDiff),
          canApply: selected ? projectApplyAllowed(selected) : false,
        })}
      />

      {error ? (
        <ErrorNotice
          title={projectsErrorTitle(error)}
          message={error}
          className="mt-2"
          onRetry={() => void refresh()}
        />
      ) : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-2">
          {notice}
        </Callout>
      ) : null}

      <div className="project-workbench">
        <div className="project-board-pane">
          <ProjectBoard
            projects={projects}
            loading={listLoading}
            selectedId={selectedId}
            filter={filter}
            query={query}
            onQueryChange={setQuery}
            onFilterChange={setFilter}
            onSelect={(project) => {
              rememberSelection(project.id);
            }}
            onCreate={() => {
              setSelectedId(null);
              setCreating(true);
              setNotice(null);
            }}
          />
        </div>
        <div className="project-detail-pane space-y-4">
          {showCreate ? (
            <ProjectCreateCard
              name={name}
              templateId={templateId}
              busy={busy === "create"}
              canSubmit={canMutate}
              submitBlockedReason={mutateBlocked}
              onNameChange={setName}
              onTemplateChange={setTemplateId}
              onSubmit={onCreate}
            />
          ) : null}
          {selected ? (
            <>
              <ProjectDetail
                connectionId={connectionId}
                project={selected}
                applyBlocked={projectApplyBlocked(selected)}
                busy={busy !== null}
                canDelete={canMutate}
                deleteBlocked={mutateBlocked}
                onDelete={() => void onDelete(selected)}
              />
              <ProjectApplyBar
                project={selected}
                busy={busy}
                canMutate={canMutate}
                canApply={projectApplyAllowed(selected)}
                applyBlocked={projectApplyBlocked(selected)}
                mutateBlocked={mutateBlocked}
                hasDiff={Boolean(selectedDiff)}
                onReview={() => void onDiff(selected)}
                onApply={() => {
                  setApplyTarget(selected);
                  setConfirmOpen(true);
                }}
                onArchive={() => void onArchive(selected)}
              />
              {selectedDiff ? <ProjectDiffPanel diff={selectedDiff} /> : null}
              <ProjectHistory
                connectionId={connectionId}
                project={selected}
                snapshots={snapshots}
                busy={busy !== null}
                onRollback={(id) => void onRollback(id)}
              />
            </>
          ) : null}
        </div>
      </div>

      <ProjectHandoffBar
        connectionId={connectionId}
        projectId={selected?.id}
        designerModel={firstCustomModel(selected?.spec_json)}
      />

      <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
        snapshotNote={applySnapshotNote()}
        title="Apply draft to Odoo"
        warning={
          applyTarget
            ? `Apply “${applyTarget.name}” — creates missing models and fields on this connection.`
            : "Apply draft project"
        }
        risks={applyRisks()}
        phrase={confirmPhrase}
        busy={busy === "apply"}
        onCancel={() => {
          setConfirmOpen(false);
          setApplyTarget(null);
        }}
        onConfirm={(phrase) => doApply(phrase)}
      />
    </ProjectShell>
  );
}

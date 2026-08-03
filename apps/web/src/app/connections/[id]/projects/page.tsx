"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ProjectDiffPanel } from "@/components/projects/ProjectDiffPanel";
import { SuggestTemplateButton } from "@/components/SuggestTemplateButton";
import { SaveAsComponentButton } from "@/components/SaveAsComponentButton";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card, EmptyState, PageHeader } from "@/components/ui/layout-primitives";
import { EMPTY_STATES } from "@/lib/copy-guide";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  FeatureGatedError,
  ProjectDiffOut,
} from "@/lib/api";
import { useEntitlements } from "@/lib/useEntitlements";
import { useUpgrade } from "@/lib/upgrade-context";
import {
  mutationAllowed,
  mutationBlockedReason,
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
} from "@/lib/capabilities";

const CONFIRM_PHRASE = "I understand the risks";

type ProjectRow = {
  id: string;
  name: string;
  template_id: string | null;
  status: string;
  lifecycle_status?: string;
  spec_json: Record<string, unknown>;
  created_at?: string | null;
};

export default function ProjectsPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [name, setName] = useState("Library draft");
  const [templateId, setTemplateId] = useState("library");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [applyTarget, setApplyTarget] = useState<ProjectRow | null>(null);
  const [confirmPhrase, setConfirmPhrase] = useState(CONFIRM_PHRASE);
  const [diffTargetId, setDiffTargetId] = useState<string | null>(null);
  const [diff, setDiff] = useState<ProjectDiffOut | null>(null);
  const { data: entitlements } = useEntitlements();
  const { openUpgrade } = useUpgrade();

  const refresh = useCallback(async () => {
    const [conn, rows] = await Promise.all([
      api.getConnection(connectionId),
      api.listProjects(connectionId),
    ]);
    setConnection(conn);
    setProjects(rows);
  }, [connectionId]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
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
    } catch (err) {
      if (err instanceof FeatureGatedError) {
        openUpgrade(err.featureKey);
      }
      setError(err instanceof Error ? err.message : "Create project failed");
    } finally {
      setBusy(false);
    }
  }

  async function doApply(phrase: string) {
    if (!applyTarget) return;
    setBusy(true);
    setError(null);
    setNotice(null);
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
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmPhrase(err.confirm_phrase || CONFIRM_PHRASE);
        setConfirmOpen(true);
        setError(err.warning || err.message);
      } else {
        setError(err instanceof Error ? err.message : "Apply failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function onDiff(project: ProjectRow) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const report = await api.projectDiff(connectionId, project.id);
      setDiffTargetId(project.id);
      setDiff(report);
      setNotice(report.message || "Diff ready");
    } catch (err) {
      setDiff(null);
      setDiffTargetId(null);
      setError(err instanceof Error ? err.message : "Diff failed");
    } finally {
      setBusy(false);
    }
  }

  const canMutate = mutationAllowed(connection);
  const mutateBlocked = mutationBlockedReason(connection);

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

  return (
    <div className="mx-auto max-w-3xl" data-testid="projects-page">
      <PageHeader
        title="Draft projects"
        description={`${connection?.name ?? connectionId} · ModuleSpec drafts, diff vs live, apply with dry-run honesty`}
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      {mutateBlocked ? (
        <Callout variant="warning" title="Mutations blocked" className="mt-4">
          {mutateBlocked}
        </Callout>
      ) : null}

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      {entitlements?.active_project_limit != null ? (
        <Callout variant="info" title="Active project slots" className="mt-4">
          {entitlements.active_projects} of {entitlements.active_project_limit} active — archive anytime to free a
          slot; history stays readable. Un-archive whenever you have a free slot.
        </Callout>
      ) : null}

      <Card className="mt-8 p-6">
        <form onSubmit={onCreate} className="space-y-4">
          <h2 className="text-xl font-semibold text-ink">New draft</h2>
          <Input
            label="Name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Select
            label="Template"
            options={[
              { value: "library", label: "library (portable ModuleSpec)" },
              { value: "", label: "blank" },
            ]}
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
          />
          <Button
            type="submit"
            variant="primary"
            disabled={busy || !canMutate}
            title={mutateBlocked ?? undefined}
            loading={busy}
          >
            Create from template
          </Button>
        </form>
      </Card>

      <ul className="mt-8 space-y-4">
        {projects.map((p) => {
          const models = Array.isArray(p.spec_json?.models)
            ? (p.spec_json.models as unknown[]).length
            : 0;
          const canApply = projectApplyAllowed(p);
          const applyBlocked = projectApplyBlocked(p);
          return (
            <li key={p.id} className="space-y-3">
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-lg font-semibold text-ink">{p.name}</p>
                  <p className="text-xs text-muted">
                    {p.status} · {p.lifecycle_status ?? "active"} · {p.template_id ?? "custom"} · {models} model(s) ·{" "}
                    <span className="font-mono">{p.id.slice(0, 8)}</span>
                  </p>
                  {applyBlocked ? (
                    <p className="mt-1 text-xs text-warning">{applyBlocked}</p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" size="sm" asChild>
                    <Link href={`/connections/${connectionId}/modulespec?project=${p.id}`}>
                      Edit ModuleSpec
                    </Link>
                  </Button>
                  {models > 0 ? (
                    <>
                      <SuggestTemplateButton
                        spec={p.spec_json}
                        connectionId={connectionId}
                        projectId={p.id}
                        disabled={busy}
                      />
                      {(p.spec_json as { _component?: boolean; grain?: string })._component ||
                      ((p.spec_json as { grain?: string }).grain &&
                        (p.spec_json as { grain?: string }).grain !== "full_app") ? (
                        <SaveAsComponentButton
                          spec={p.spec_json as Record<string, unknown>}
                          disabled={busy}
                        />
                      ) : null}
                    </>
                  ) : null}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={busy || !canMutate}
                    title={mutateBlocked ?? undefined}
                    onClick={() => onDiff(p)}
                  >
                    Diff vs live
                  </Button>
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    disabled={busy || !canApply}
                    title={applyBlocked ?? undefined}
                    onClick={() => {
                      setApplyTarget(p);
                      setConfirmOpen(true);
                    }}
                  >
                    Apply
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        if ((p.lifecycle_status ?? "active") === "archived") {
                          await api.unarchiveProject(connectionId, p.id);
                        } else {
                          await api.archiveProject(connectionId, p.id);
                        }
                        await refresh();
                      } catch (err) {
                        if (err instanceof FeatureGatedError) openUpgrade(err.featureKey);
                        setError(err instanceof Error ? err.message : "Archive failed");
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {(p.lifecycle_status ?? "active") === "archived" ? "Un-archive" : "Archive"}
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    disabled={busy || !canMutate}
                    title={mutateBlocked ?? undefined}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await api.deleteProject(connectionId, p.id);
                        if (diffTargetId === p.id) {
                          setDiff(null);
                          setDiffTargetId(null);
                        }
                        await refresh();
                      } catch (err) {
                        setError(err instanceof Error ? err.message : "Delete failed");
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </Card>
              {diff && diffTargetId === p.id ? <ProjectDiffPanel diff={diff} /> : null}
            </li>
          );
        })}
        {projects.length === 0 ? (
          <EmptyState
            title="No drafts yet"
            description={EMPTY_STATES.projects}
          />
        ) : null}
      </ul>

      <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
        snapshotNote="A metadata snapshot is taken before apply when the API supports it."
        title="Apply draft to Odoo"
        warning={
          applyTarget
            ? `Apply “${applyTarget.name}” — creates missing models and fields on this connection.`
            : "Apply draft project"
        }
        risks={[
          "Creates ir.model / ir.model.fields on the live target",
          "v1 apply does not create views/menus/ACL from the draft",
          "Prefer a sandbox connection",
        ]}
        phrase={confirmPhrase}
        busy={busy}
        onCancel={() => {
          setConfirmOpen(false);
          setApplyTarget(null);
        }}
        onConfirm={(phrase) => doApply(phrase)}
      />
    </div>
  );
}

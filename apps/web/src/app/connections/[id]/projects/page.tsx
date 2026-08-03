"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { SuggestTemplateButton } from "@/components/SuggestTemplateButton";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  ProjectDiffOut,
} from "@/lib/api";
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
    // Library template drafts may include loan object_write automation.
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
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#3d2a38_0%,_#1a1218_50%,_#0c090b_100%)] px-6 py-10 text-[#f4eef2]">
      <div className="mx-auto max-w-3xl">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[#c9a9c0] hover:underline">
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/builder`}
            className="text-[#8f7a88] hover:underline"
          >
            Builder
          </Link>
          <Link
            href={`/connections/${connectionId}/reminders`}
            className="text-[#8f7a88] hover:underline"
          >
            Reminders
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Draft projects
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          {connection?.name ?? connectionId} · visual ModuleSpec editor, Code→UI import,
          then Apply / Generate UI
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />
        {mutateBlocked && (
          <p className="mt-2 text-sm text-[#e8d09f]">{mutateBlocked}</p>
        )}

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}
        {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}

        <form
          onSubmit={onCreate}
          className="mt-8 space-y-4 border border-[#3d2a38] bg-[#0f1a16]/70 p-6"
        >
          <h2 className="font-[family-name:var(--font-display)] text-xl">New draft</h2>
          <label className="block text-sm">
            <span className="text-[#a8909e]">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-[#a8909e]">Template</span>
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            >
              <option value="library">library (portable ModuleSpec)</option>
              <option value="">blank</option>
            </select>
          </label>
          <button
            type="submit"
            disabled={busy || !canMutate}
            title={mutateBlocked ?? undefined}
            className="h-11 bg-[#714B67] px-5 text-sm font-semibold text-white disabled:opacity-60"
          >
            Create from template
          </button>
        </form>

        <ul className="mt-8 space-y-3">
          {projects.map((p) => {
            const models = Array.isArray(p.spec_json?.models)
              ? (p.spec_json.models as unknown[]).length
              : 0;
            const canApply = projectApplyAllowed(p);
            const applyBlocked = projectApplyBlocked(p);
            return (
              <li key={p.id} className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3 border border-[#3d2a38] bg-[#0f1a16]/50 px-4 py-3">
                  <div>
                    <p className="font-[family-name:var(--font-display)] text-lg text-[#faf6f9]">
                      {p.name}
                    </p>
                    <p className="text-xs text-[#8f7a88]">
                      {p.status} · {p.template_id ?? "custom"} · {models} model(s) ·{" "}
                      <span className="font-mono">{p.id.slice(0, 8)}</span>
                    </p>
                    {applyBlocked && (
                      <p className="mt-1 text-xs text-[#e8d09f]">{applyBlocked}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href={`/connections/${connectionId}/modulespec?project=${p.id}`}
                      className="border border-[#c9a96e] px-3 py-1.5 text-sm text-[#c9a96e]"
                    >
                      Edit ModuleSpec
                    </Link>
                    {models > 0 && (
                      <SuggestTemplateButton
                        spec={p.spec_json}
                        connectionId={connectionId}
                        projectId={p.id}
                        disabled={busy}
                      />
                    )}
                    {models > 0 && (
                      <SuggestTemplateButton
                        spec={p.spec_json}
                        connectionId={connectionId}
                        projectId={p.id}
                        disabled={busy}
                      />
                    )}
                    <button
                      type="button"
                      disabled={busy || !canMutate}
                      title={mutateBlocked ?? undefined}
                      className="border border-[#3d2a38] px-3 py-1.5 text-sm text-[#d4c4ce] disabled:opacity-50"
                      onClick={() => onDiff(p)}
                    >
                      Diff vs live
                    </button>
                    <button
                      type="button"
                      disabled={busy || !canApply}
                      title={applyBlocked ?? undefined}
                      className="border border-[#c9a9c0] px-3 py-1.5 text-sm text-[#c9a9c0] disabled:opacity-50"
                      onClick={() => {
                        setApplyTarget(p);
                        setConfirmOpen(true);
                      }}
                    >
                      Apply
                    </button>
                    <button
                      type="button"
                      disabled={busy || !canMutate}
                      title={mutateBlocked ?? undefined}
                      className="border border-[#f0a8a0] px-3 py-1.5 text-sm text-[#f0a8a0] disabled:opacity-50"
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
                    </button>
                  </div>
                </div>
                {diff && diffTargetId === p.id && (
                  <div className="border border-[#3d2a38] bg-[#0c090b]/80 px-4 py-3 text-sm">
                    <p className="text-[#c9a9c0]">{diff.message || "Diff"}</p>
                    {diff.conflicts.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs uppercase text-[#f0a8a0]">Conflicts</p>
                        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[#f0a8a0]">
                          {diff.conflicts.map((c) => (
                            <li key={c}>{c}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {diff.to_create_models.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs uppercase text-[#8f7a88]">Models to create</p>
                        <ul className="mt-1 list-disc space-y-0.5 pl-5 font-mono text-[#c9a9c0]">
                          {diff.to_create_models.map((m) => (
                            <li key={m}>{m}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {diff.to_create_fields.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs uppercase text-[#8f7a88]">Fields to create</p>
                        <ul className="mt-1 list-disc space-y-0.5 pl-5 font-mono text-[#c9a9c0]">
                          {diff.to_create_fields.map((f) => (
                            <li key={f}>{f}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {diff.existing_models.length > 0 && (
                      <p className="mt-2 text-xs text-[#8f7a88]">
                        Existing models: {diff.existing_models.join(", ")}
                      </p>
                    )}
                  </div>
                )}
              </li>
            );
          })}
          {projects.length === 0 && (
            <li className="text-sm text-[#8f7a88]">No drafts yet.</li>
          )}
        </ul>
      </div>

      <ConfirmDialog
        open={confirmOpen}
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
    </main>
  );
}

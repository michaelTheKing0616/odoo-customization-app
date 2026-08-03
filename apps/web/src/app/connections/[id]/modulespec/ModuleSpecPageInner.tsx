"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/layout-primitives";
import {
  ModuleSpecDoc,
  ModuleSpecEditor,
} from "@/components/ModuleSpecEditor";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  api,
  ConfirmationRequiredError,
  Connection,
} from "@/lib/api";
import {
  mutationAllowed,
  mutationBlockedReason,
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
  connectionSupports,
} from "@/lib/capabilities";

const CONFIRM_PHRASE = "I understand the risks";
const DRAFT_KEY = (cid: string) => `modulespec-draft:${cid}`;

export default function ModuleSpecPageInner() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const connectionId = params.id;
  const projectId = search.get("project");

  const [connection, setConnection] = useState<Connection | null>(null);
  const [spec, setSpec] = useState<ModuleSpecDoc>({
    technical_name: "custom_app",
    display_name: "Custom App",
    depends: ["base"],
    models: [],
  });
  const [hydrated, setHydrated] = useState(false);
  const sessionHydratedRef = useRef(false);
  const [projectName, setProjectName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [genConfirmOpen, setGenConfirmOpen] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const conn = await api.getConnection(connectionId);
      setConnection(conn);
      if (projectId) {
        const p = await api.getProject(connectionId, projectId);
        setProjectName(p.name);
        setSpec((p.spec_json || {}) as ModuleSpecDoc);
        return;
      }
      // Hydrate from session only once — re-running would remount inputs mid-typing
      // and overwrite in-progress edits (focus lost after each character).
      if (!sessionHydratedRef.current) {
        sessionHydratedRef.current = true;
        try {
          const raw = sessionStorage.getItem(DRAFT_KEY(connectionId));
          if (raw) {
            const parsed = JSON.parse(raw) as ModuleSpecDoc;
            setSpec(parsed);
            const modelCount = Array.isArray(parsed.models) ? parsed.models.length : 0;
            setNotice(
              modelCount > 0
                ? `Restored ModuleSpec from this browser session (${modelCount} model(s)).`
                : "Restored session draft — but it has 0 models. Go back to Wizard, re-draft, then Open in ModuleSpec again.",
            );
          }
        } catch {
          /* ignore corrupt session JSON */
        }
      }
    } finally {
      setHydrated(true);
    }
  }, [connectionId, projectId]);

  useEffect(() => {
    sessionHydratedRef.current = false;
    setHydrated(false);
  }, [connectionId, projectId]);

  useEffect(() => {
    load().catch((err: Error) => {
      setError(err.message);
      setHydrated(true);
    });
  }, [load]);

  // Do not persist until load() finishes — otherwise the empty default
  // { models: [] } overwrites the Wizard AI draft in sessionStorage.
  useEffect(() => {
    if (!hydrated || projectId) return;
    try {
      sessionStorage.setItem(DRAFT_KEY(connectionId), JSON.stringify(spec));
    } catch {
      /* ignore */
    }
  }, [spec, connectionId, projectId, hydrated]);

  async function onSaveProject() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (projectId) {
        await api.updateProject(connectionId, projectId, {
          spec_json: spec as Record<string, unknown>,
        });
        setNotice("Project ModuleSpec saved.");
      } else {
        const created = await api.createProject(connectionId, {
          name: String(spec.display_name || "ModuleSpec draft"),
          template_id: null,
          spec_json: spec as Record<string, unknown>,
        });
        setNotice(`Saved as project ${created.name}`);
        window.location.href = `/connections/${connectionId}/modulespec?project=${created.id}`;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onImportFile(file: File) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.importModuleSpec(file);
      setSpec(res.spec as ModuleSpecDoc);
      setImportWarnings(res.warnings || []);
      setNotice(
        `Imported (${res.source}): review models/unmapped, then save or Generate UI.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  async function onGenerateUi(phrase: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.applyModuleSpec(connectionId, {
        spec: spec as Record<string, unknown>,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setGenConfirmOpen(false);
      setNotice(res.message);
      if (res.warnings?.length) setImportWarnings(res.warnings);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Generate UI failed");
      }
    } finally {
      setBusy(false);
    }
  }

  const canSave = mutationAllowed(connection);
  const saveBlocked = mutationBlockedReason(connection);
  const applyOpts = scaffoldOptsFromSpec(spec as Record<string, unknown>);
  const canApply = scaffoldApplyAllowed(connection, applyOpts);
  const applyBlocked = scaffoldApplyBlockedReason(connection, applyOpts);
  const barcodeModuleAllowed = connectionSupports(connection, "barcode_scan_module");

  return (
    <div className="mx-auto max-w-6xl" data-testid="modulespec-page">
      <PageHeader
        title="ModuleSpec builder"
        description={`${connection?.name ?? connectionId}${projectName ? ` · project “${projectName}”` : " · session draft"} — single contract for AI drafts, Code→UI import, and Generate UI.`}
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      {(applyBlocked || saveBlocked) ? (
        <Callout variant="warning" title="Blocked" className="mt-4">
          {applyBlocked ?? saveBlocked}
        </Callout>
      ) : null}

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}
        {importWarnings.length > 0 && (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-warning">
            {importWarnings.slice(0, 10).map((w, i) => (
              <li key={`${i}-${w}`}>{w}</li>
            ))}
          </ul>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <label className="cursor-pointer border border-warning px-3 py-1.5 text-sm text-warning">
            {busy ? "Working…" : "Import zip / .py / .xml / .meta.json"}
            <input
              type="file"
              accept=".zip,.py,.xml,.json"
              className="hidden"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void onImportFile(f);
                e.target.value = "";
              }}
            />
          </label>
          <button
            type="button"
            disabled={busy || !canSave}
            title={saveBlocked ?? undefined}
            onClick={() => onSaveProject()}
            className="border border-accent px-3 py-1.5 text-sm text-muted disabled:opacity-50"
          >
            {projectId ? "Save project" : "Save as project"}
          </button>
          <button
            type="button"
            disabled={
              busy ||
              !Array.isArray(spec.models) ||
              spec.models.length === 0 ||
              !canApply
            }
            title={applyBlocked ?? undefined}
            onClick={() => setGenConfirmOpen(true)}
            className="bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Generate UI from ModuleSpec
          </button>
        </div>

        {barcodeModuleAllowed ? (
          <label className="mt-4 flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={Boolean(spec.include_barcode_scan_widget)}
              onChange={(e) =>
                setSpec({ ...spec, include_barcode_scan_widget: e.target.checked })
              }
            />
            Include exported <code className="text-xs">x_barcode_scan</code> OWL widget module
            (our add-on — not native Odoo; Apache-2 ZXing attribution in README)
          </label>
        ) : (
          <p className="mt-4 text-xs text-muted">
            Exported barcode widget module is unavailable on Odoo Online — use Bulk Suite in-app
            scanner instead.
          </p>
        )}

        <div className="mt-6">
          <ModuleSpecEditor value={spec} onChange={setSpec} />
        </div>

      <ConfirmDialogV2
        open={genConfirmOpen}
        riskLevel="danger"
        title="Generate UI from ModuleSpec"
        warning="Creates models, fields, views, menus, and smart buttons on this live Odoo connection."
        risks={[
          "Live metadata writes on custom x_* models",
          "Smart buttons use inherit views (stock forms like Contacts stay intact)",
          "Prefer sandbox first",
          "Automations remain review-only",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setGenConfirmOpen(false)}
        onConfirm={onGenerateUi}
      />
    </div>
  );
}

"use client";

import { Button } from "@/components/ui/Button";
import type { ModuleSpecBusy } from "@/lib/modulespec-journey";

type ModuleSpecApplyBarProps = {
  busy: ModuleSpecBusy;
  canSave: boolean;
  canApply: boolean;
  canValidate: boolean;
  hasModels: boolean;
  hasContent: boolean;
  stockReuse: boolean;
  projectId?: string | null;
  saveBlocked?: string | null;
  applyBlocked?: string | null;
  odooAppUrl?: string | null;
  canDevCode?: boolean;
  onImportFile: (file: File) => void;
  onSaveProject: () => void;
  onGenerateUi: () => void;
  onDownloadZip: () => void;
  onExportSandbox?: () => void;
  onWalkthrough?: () => void;
};

export function ModuleSpecApplyBar({
  busy,
  canSave,
  canApply,
  canValidate,
  hasModels,
  hasContent,
  stockReuse,
  projectId,
  saveBlocked,
  applyBlocked,
  odooAppUrl,
  canDevCode,
  onImportFile,
  onSaveProject,
  onGenerateUi,
  onDownloadZip,
  onExportSandbox,
  onWalkthrough,
}: ModuleSpecApplyBarProps) {
  const working = busy !== null;
  return (
    <div className="flex flex-wrap gap-2" data-testid="modulespec-apply-bar">
      <label className="inline-flex">
        <Button type="button" variant="secondary" size="sm" disabled={working} asChild>
          <span>{busy === "import" ? "Importing…" : "Import zip or JSON"}</span>
        </Button>
        <input
          type="file"
          accept=".zip,.py,.xml,.json"
          className="hidden"
          disabled={working}
          data-testid="modulespec-import"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onImportFile(file);
            event.target.value = "";
          }}
        />
      </label>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={working || !canSave}
        title={saveBlocked ?? undefined}
        loading={busy === "save"}
        onClick={onSaveProject}
        data-testid="modulespec-save-project"
      >
        {projectId ? "Save project" : "Save as project"}
      </Button>
      <Button
        type="button"
        variant={stockReuse ? "secondary" : "primary"}
        size="sm"
        disabled={working || !hasModels || !canApply || stockReuse}
        title={
          stockReuse
            ? "No custom ModuleSpec to apply — use Job Autopilot"
            : (applyBlocked ?? undefined)
        }
        loading={busy === "apply"}
        onClick={onGenerateUi}
        data-testid="modulespec-generate-ui"
      >
        Generate UI
      </Button>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={working || !hasContent || stockReuse}
        loading={busy === "zip"}
        onClick={onDownloadZip}
        data-testid="modulespec-download-zip"
      >
        Download zip
      </Button>
      {canDevCode && onExportSandbox ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={working || !hasContent}
          loading={busy === "sandbox"}
          onClick={onExportSandbox}
          data-testid="modulespec-sandbox"
        >
          Export and sandbox-test
        </Button>
      ) : null}
      {odooAppUrl ? (
        <>
          <Button asChild size="sm">
            <a href={odooAppUrl} target="_blank" rel="noopener noreferrer" data-testid="open-app-in-odoo">
              Open app in Odoo
            </a>
          </Button>
          {onWalkthrough ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={working || !canApply}
              loading={busy === "walkthrough"}
              onClick={onWalkthrough}
              data-testid="modulespec-walkthrough"
            >
              Load demo walkthrough
            </Button>
          ) : null}
        </>
      ) : null}
      <span className="sr-only">{canValidate ? "Validate available" : "Validate gated"}</span>
    </div>
  );
}

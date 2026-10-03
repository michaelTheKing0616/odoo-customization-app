"use client";

import {
  api,
  ConfirmationRequiredError,
  type AppTemplate,
  type ScaffoldResult,
} from "@/lib/api";
import { reportApiError } from "@/lib/api-error";

type UseWizardScaffoldArgs = {
  connectionId: string;
  selected: AppTemplate | null;
  displayName: string;
  technicalPrefix: string;
  multiCompany: boolean;
  setSelected: (value: AppTemplate | null) => void;
  setDisplayName: (value: string) => void;
  setResult: (value: ScaffoldResult | null) => void;
  setError: (value: string | null) => void;
  setConfirmOpen: (value: boolean) => void;
  setBusy: (value: boolean) => void;
  setAiNote: (value: string | null) => void;
};

export function useWizardScaffold({
  connectionId,
  selected,
  displayName,
  technicalPrefix,
  multiCompany,
  setSelected,
  setDisplayName,
  setResult,
  setError,
  setConfirmOpen,
  setBusy,
  setAiNote,
}: UseWizardScaffoldArgs) {
  function openConfirm(tpl: AppTemplate) {
    setSelected(tpl);
    setResult(null);
    setError(null);
    if (!displayName.trim()) {
      setDisplayName(tpl.name);
    }
    setConfirmOpen(true);
  }

  async function onConfirmScaffold(phrase: string) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const prefix = technicalPrefix.trim();
      const res = await api.scaffoldApp(connectionId, {
        template_id: selected.id,
        display_name: displayName.trim() || selected.name,
        ...(prefix ? { technical_prefix: prefix } : {}),
        multi_company: multiCompany,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setResult(res);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        reportApiError(err, setError, { fallback: "Scaffold failed", toast: true });
      }
    } finally {
      setBusy(false);
    }
  }

  async function onExportLibraryWithFines() {
    setBusy(true);
    setError(null);
    try {
      const mod = await api.exportLibraryModule({
        technical_name: "library_mgmt",
        display_name: displayName.trim() || "Library Management",
        fines: true,
        reminders: true,
        multi_company: multiCompany,
      });
      const bin = Uint8Array.from(atob(mod.content_base64), (c) =>
        c.charCodeAt(0),
      );
      const blob = new Blob([bin], { type: "application/zip" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = mod.filename;
      a.click();
      URL.revokeObjectURL(url);
      setAiNote(mod.note);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Export failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  return { openConfirm, onConfirmScaffold, onExportLibraryWithFines };
}

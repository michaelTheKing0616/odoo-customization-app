"use client";

import { useState } from "react";
import { api } from "@/lib/api";

type Props = {
  spec: Record<string, unknown>;
  connectionId?: string;
  projectId?: string;
  disabled?: boolean;
  className?: string;
};

export function SuggestTemplateButton({
  spec,
  connectionId,
  projectId,
  disabled,
  className = "border border-border-subtle px-3 py-1.5 text-sm text-muted disabled:opacity-50",
}: Props) {
  const [open, setOpen] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    filename: string;
    source: string;
    domain_pack: string;
    note: string;
    warnings: string[];
  } | null>(null);

  async function onGenerate() {
    if (!consent) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.generalizePack({
        spec_json: projectId ? undefined : spec,
        project_id: projectId,
        connection_id: connectionId,
        consent_share_template: true,
      });
      setResult({
        filename: res.filename,
        source: res.source,
        domain_pack: res.domain_pack,
        note: res.note,
        warnings: res.warnings ?? [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generalize failed");
    } finally {
      setBusy(false);
    }
  }

  function onDownload() {
    if (!result) return;
    const blob = new Blob([result.source], { type: "text/x-python" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <button
        type="button"
        disabled={disabled || busy}
        className={className}
        onClick={() => {
          setOpen(true);
          setConsent(false);
          setResult(null);
          setError(null);
        }}
      >
        {busy ? "Generating…" : "Suggest as template"}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-surface/80 px-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto border border-border-subtle bg-surface-raised p-5">
            <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
              Suggest as template
            </h2>
            {!result ? (
              <>
                <p className="mt-2 text-sm text-muted">
                  With your permission, we generalize this ModuleSpec structure (model
                  names, fields, workflows, automations) into a candidate domain-pack file
                  for human review. Customer record data is not included. The file is
                  download-only and is never auto-registered in the app.
                </p>
                <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
                  <li>Operational patterns may be reused in the shared template library</li>
                  <li>You review and commit the Python file manually if approved</li>
                  <li>No live Odoo changes from this action</li>
                </ul>
                <label className="mt-4 flex items-start gap-2 text-sm text-muted">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    className="mt-1"
                  />
                  <span>
                    I agree to share this structure for template library review (structure
                    only, not customer data).
                  </span>
                </label>
                {error && <p className="mt-3 text-sm text-danger">{error}</p>}
                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={!consent || busy}
                    onClick={() => onGenerate()}
                    className="border border-border-subtle px-3 py-1.5 text-sm text-muted disabled:opacity-50"
                  >
                    {busy ? "Generating…" : "Generate candidate pack"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="text-sm text-muted hover:underline"
                  >
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="mt-2 text-sm text-muted">{result.note}</p>
                <p className="mt-1 font-mono text-xs text-muted">
                  {result.filename} · domain_pack={result.domain_pack}
                </p>
                {result.warnings.length > 0 && (
                  <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-[#e8d09f]">
                    {result.warnings.slice(0, 6).map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                )}
                <textarea
                  readOnly
                  value={result.source}
                  rows={12}
                  className="mt-3 w-full border border-border-subtle bg-surface p-2 font-mono text-xs text-ink"
                />
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={onDownload}
                    className="border border-[#c9a96e] px-3 py-1.5 text-sm text-[#c9a96e]"
                  >
                    Download .py
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void navigator.clipboard.writeText(result.source);
                    }}
                    className="border border-border-subtle px-3 py-1.5 text-sm text-muted"
                  >
                    Copy source
                  </button>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="text-sm text-muted hover:underline"
                  >
                    Close
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";

type Props = {
  spec: Record<string, unknown>;
  disabled?: boolean;
  className?: string;
};

export function SaveAsComponentButton({ spec, disabled, className }: Props) {
  const [open, setOpen] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    filename: string;
    source: string;
    domain_pack: string;
    host_slot: string;
    note: string;
    warnings: string[];
  } | null>(null);

  const hostSlot =
    (spec.connect_points as { host_model?: string } | undefined)?.host_model ||
    (Array.isArray(spec.models)
      ? (spec.models as Array<{ mode?: string; model?: string }>).find(
          (m) => m.mode === "inherit",
        )?.model
      : undefined) ||
    "any";

  async function onGenerate() {
    if (!consent) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.generalizeComponent({
        spec_json: spec,
        consent_share_template: true,
        host_slot: hostSlot,
        pack_slug:
          typeof spec.gallery_id === "string"
            ? spec.gallery_id
            : typeof spec.technical_name === "string"
              ? spec.technical_name
              : undefined,
      });
      setResult({
        filename: res.filename,
        source: res.source,
        domain_pack: res.domain_pack,
        host_slot: res.host_slot,
        note: res.note,
        warnings: res.warnings ?? [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save as component failed");
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
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={disabled || busy}
        className={className}
        onClick={() => {
          setOpen(true);
          setConsent(false);
          setResult(null);
          setError(null);
        }}
      >
        {busy ? "Saving…" : "Save as component"}
      </Button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-md border border-border-subtle bg-surface-raised p-5">
            <h2 className="text-xl font-semibold text-ink">Save as component template</h2>
            {!result ? (
              <>
                <p className="mt-2 text-sm text-muted">
                  Generalize this component ModuleSpec into a reusable gallery candidate
                  (host slot <span className="font-mono">{hostSlot}</span>). Download-only —
                  never auto-registered.
                </p>
                <label className="mt-4 flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    className="mt-1"
                  />
                  <span>I agree to export this structure for gallery review (no customer data).</span>
                </label>
                {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
                <div className="mt-5 flex flex-wrap gap-3">
                  <Button
                    type="button"
                    variant="primary"
                    disabled={!consent || busy}
                    loading={busy}
                    onClick={() => void onGenerate()}
                  >
                    Generate template
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                    Cancel
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p className="mt-2 text-sm text-ink">{result.note}</p>
                <p className="mt-1 font-mono text-xs text-muted">
                  {result.filename} · {result.domain_pack} · host={result.host_slot}
                </p>
                {result.warnings.length > 0 ? (
                  <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-warning">
                    {result.warnings.slice(0, 6).map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                ) : null}
                <textarea
                  readOnly
                  value={result.source}
                  rows={12}
                  className="mt-3 w-full rounded border border-border-subtle bg-surface p-2 font-mono text-xs"
                />
                <div className="mt-4 flex flex-wrap gap-3">
                  <Button type="button" variant="primary" onClick={onDownload}>
                    Download .py
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => void navigator.clipboard.writeText(result.source)}
                  >
                    Copy source
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                    Close
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

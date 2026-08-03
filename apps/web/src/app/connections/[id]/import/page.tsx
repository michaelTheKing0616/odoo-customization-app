"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  DataImportCommitOut,
  ImageImportCommitOut,
  ImageImportPreviewOut,
} from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";

const CONFIRM_PHRASE = "I understand the risks";

function SeedPackPicker({
  connectionId,
  onPick,
}: {
  connectionId: string;
  onPick: (model: string, csv: string) => void;
}) {
  const [packs, setPacks] = useState<
    Array<{ id: string; name: string; description: string; models: string[] }>
  >([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listSeedPacks(connectionId)
      .then(setPacks)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  if (error) return <p className="text-xs text-[#f0a8a0]">{error}</p>;
  if (!packs.length) return <p className="text-xs text-[var(--odoo-muted)]">Loading packs…</p>;

  return (
    <ul className="space-y-3">
      {packs.map((p) => (
        <li key={p.id} className="border border-[var(--odoo-border)] p-3 text-sm">
          <p className="font-medium">{p.name}</p>
          <p className="text-xs text-[var(--odoo-muted)]">{p.description}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {p.models.map((m) => (
              <button
                key={m}
                type="button"
                className="border border-[var(--odoo-primary)] px-2 py-1 font-mono text-xs text-[var(--odoo-primary)]"
                onClick={async () => {
                  const detail = await api.getSeedPack(connectionId, p.id);
                  const entry = detail.models.find((x) => x.model === m);
                  if (entry) onPick(entry.model, entry.csv);
                }}
              >
                {m}
              </button>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function DataImportPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [model, setModel] = useState("res.partner");
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"create" | "upsert">("create");
  const [matchFields, setMatchFields] = useState("email");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<DataImportCommitOut | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [imgManifest, setImgManifest] = useState<File | null>(null);
  const [imgZip, setImgZip] = useState<File | null>(null);
  const [imgPreview, setImgPreview] = useState<ImageImportPreviewOut | null>(null);
  const [imgMatchField, setImgMatchField] = useState("x_name");
  const [imgField, setImgField] = useState("");
  const [imgResult, setImgResult] = useState<ImageImportCommitOut | null>(null);
  const [imgConfirmOpen, setImgConfirmOpen] = useState(false);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  const sample = useMemo(() => rows.slice(0, 5), [rows]);

  async function onPreview() {
    if (!file) {
      setError("Choose a CSV or XLSX file first");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const preview = await api.dataImportPreview(connectionId, file, model);
      setHeaders(preview.headers);
      setRows(preview.sample_rows);
      setMapping(preview.suggested_mapping);
      if (preview.suggested_model) setModel(preview.suggested_model);
      setNotice(`Parsed ${preview.row_count} row(s). Review mapping, then Dry-run.`);
      setLastResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function runCommit(dryRun: boolean, phrase?: string) {
    if (!rows.length) {
      setError("Parse a file first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.dataImportCommit(connectionId, {
        model,
        mapping,
        mode,
        match_fields:
          mode === "upsert"
            ? matchFields
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean)
            : [],
        dry_run: dryRun,
        rows,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setLastResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Commit failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function downloadTemplate() {
    const t = await api.dataImportTemplate(connectionId, model);
    const blob = new Blob([t.csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = t.filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function onImagePreview() {
    if (!imgManifest || !imgZip) {
      setError("Choose manifest CSV and images ZIP");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const preview = await api.imageImportPreview(connectionId, imgManifest, imgZip);
      setImgPreview(preview);
      setImgMatchField(preview.match_field);
      setImgField(preview.image_field);
      setImgResult(null);
      setNotice(`Image manifest: ${preview.row_count} row(s). ${preview.warnings.join(" ")}`.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function runImageCommit(dryRun: boolean, phrase?: string) {
    if (!imgManifest || !imgZip) {
      setError("Choose manifest CSV and images ZIP");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.imageImportCommit(connectionId, {
        model,
        manifest: imgManifest,
        imagesZip: imgZip,
        match_field: imgMatchField,
        image_field: imgField || undefined,
        dry_run: dryRun,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setImgResult(res);
      setNotice(res.message);
      setImgConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setImgConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Image import failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap gap-3 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[var(--odoo-primary-light)] hover:underline">
            ← Metadata
          </Link>
          <Link href={`/connections/${connectionId}/power-ops`} className="text-[var(--odoo-primary-light)] hover:underline">
            Power Ops
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[var(--odoo-sheet-fg)]">
          Bulk data import
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--odoo-muted)]">
          Upload CSV/XLSX → map columns → dry-run → create or upsert contacts, products, or any model.
          Writes require typing the risk phrase.
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />

        <section className="odoo-sheet mt-6 space-y-4 p-4">
          <h2 className="text-sm font-semibold text-[var(--odoo-primary)]">Industry seed packs</h2>
          <SeedPackPicker
            connectionId={connectionId}
            onPick={(m, csv) => {
              setModel(m);
              const blob = new Blob([csv], { type: "text/csv" });
              const file = new File([blob], `${m.replace(/\./g, "_")}_seed.csv`, {
                type: "text/csv",
              });
              setFile(file);
              setNotice(`Loaded seed for ${m} — click Parse to preview`);
            }}
          />
        </section>

        <section className="odoo-sheet mt-6 space-y-4 p-4">
          <label className="block text-sm">
            Target model
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 text-[#1f1f1f]"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="res.partner"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void downloadTemplate()}
              className="border border-[var(--odoo-primary)] px-3 py-1.5 text-sm text-[var(--odoo-primary)]"
            >
              Download template
            </button>
            <input
              type="file"
              accept=".csv,.xlsx,.xlsm,.txt"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
            <button
              type="button"
              disabled={busy || !file}
              onClick={() => void onPreview()}
              className="bg-[var(--odoo-primary)] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              Parse file
            </button>
          </div>

          {headers.length > 0 && (
            <>
              <div className="flex flex-wrap gap-4 text-sm">
                <label>
                  Mode{" "}
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value as "create" | "upsert")}
                    className="border border-[var(--odoo-border)] bg-white px-2 py-1"
                  >
                    <option value="create">create</option>
                    <option value="upsert">upsert</option>
                  </select>
                </label>
                {mode === "upsert" && (
                  <label>
                    Match fields (comma){" "}
                    <input
                      value={matchFields}
                      onChange={(e) => setMatchFields(e.target.value)}
                      className="border border-[var(--odoo-border)] bg-white px-2 py-1"
                    />
                  </label>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[var(--odoo-border)]">
                      <th className="py-1">CSV column</th>
                      <th className="py-1">Odoo field</th>
                    </tr>
                  </thead>
                  <tbody>
                    {headers.map((h) => (
                      <tr key={h} className="border-b border-[var(--odoo-border)]/60">
                        <td className="py-1 font-mono text-xs">{h}</td>
                        <td className="py-1">
                          <input
                            className="w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
                            value={mapping[h] ?? ""}
                            onChange={(e) =>
                              setMapping((m) => ({ ...m, [h]: e.target.value }))
                            }
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-[var(--odoo-muted)]">
                {rows.length} row(s) loaded. Sample:
              </p>
              <pre className="max-h-40 overflow-auto bg-[#f8f9fa] p-2 text-xs text-[#1f1f1f]">
                {JSON.stringify(sample, null, 2)}
              </pre>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void runCommit(true)}
                  className="border border-[var(--odoo-primary)] px-3 py-1.5 text-sm text-[var(--odoo-primary)] disabled:opacity-50"
                >
                  Dry-run
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setConfirmOpen(true)}
                  className="bg-[var(--odoo-danger)] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Commit writes
                </button>
              </div>
            </>
          )}

          {notice && <p className="text-sm text-[var(--odoo-success)]">{notice}</p>}
          {error && <p className="text-sm text-[var(--odoo-danger)]">{error}</p>}
          {lastResult && (
            <div className="text-sm">
              <p>
                created={lastResult.created} updated={lastResult.updated} failed=
                {lastResult.failed} skipped={lastResult.skipped}
              </p>
              {lastResult.error_csv && (
                <button
                  type="button"
                  className="mt-2 text-[var(--odoo-primary)] underline"
                  onClick={() => {
                    const blob = new Blob([lastResult.error_csv!], {
                      type: "text/csv",
                    });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "import_errors.csv";
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  Download error CSV
                </button>
              )}
            </div>
          )}
        </section>

        <section className="odoo-sheet mt-6 space-y-4 p-4" data-testid="image-import-panel">
          <h2 className="text-sm font-semibold text-[var(--odoo-primary)]">Bulk image import</h2>
          <p className="text-xs text-[var(--odoo-muted)]">
            CSV manifest (<code>match,name,filename</code>) + ZIP of images → writes base64 to an
            image/binary field. Images are downscaled server-side (max {1920}px, 5MB guard).
          </p>
          <div className="flex flex-wrap gap-2">
            <label className="text-xs">
              Manifest CSV
              <input
                type="file"
                accept=".csv,.txt"
                className="mt-1 block text-sm"
                onChange={(e) => setImgManifest(e.target.files?.[0] ?? null)}
              />
            </label>
            <label className="text-xs">
              Images ZIP
              <input
                type="file"
                accept=".zip"
                className="mt-1 block text-sm"
                onChange={(e) => setImgZip(e.target.files?.[0] ?? null)}
              />
            </label>
            <button
              type="button"
              disabled={busy || !imgManifest || !imgZip}
              onClick={() => void onImagePreview()}
              className="self-end border border-[var(--odoo-primary)] px-3 py-1.5 text-sm text-[var(--odoo-primary)] disabled:opacity-50"
            >
              Preview manifest
            </button>
          </div>
          {imgPreview && (
            <>
              <div className="grid gap-2 sm:grid-cols-2 text-sm">
                <label>
                  Match field
                  <input
                    value={imgMatchField}
                    onChange={(e) => setImgMatchField(e.target.value)}
                    className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
                  />
                </label>
                <label>
                  Image field
                  <input
                    value={imgField}
                    onChange={(e) => setImgField(e.target.value)}
                    placeholder={imgPreview.image_field}
                    className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
                  />
                </label>
              </div>
              <pre className="max-h-32 overflow-auto bg-[#f8f9fa] p-2 text-xs text-[#1f1f1f]">
                {JSON.stringify(imgPreview.sample_rows, null, 2)}
              </pre>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void runImageCommit(true)}
                  className="border border-[var(--odoo-primary)] px-3 py-1.5 text-sm text-[var(--odoo-primary)] disabled:opacity-50"
                >
                  Dry-run images
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setImgConfirmOpen(true)}
                  className="bg-[var(--odoo-danger)] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Commit image writes
                </button>
              </div>
            </>
          )}
          {imgResult && (
            <div className="overflow-x-auto text-sm" data-testid="image-import-results">
              <p>
                updated={imgResult.updated} failed={imgResult.failed} skipped={imgResult.skipped}
              </p>
              <table className="mt-2 w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[var(--odoo-border)]">
                    <th className="py-1">#</th>
                    <th className="py-1">match</th>
                    <th className="py-1">file</th>
                    <th className="py-1">ok</th>
                    <th className="py-1">error</th>
                  </tr>
                </thead>
                <tbody>
                  {imgResult.results.map((r) => (
                    <tr key={r.row_index} className="border-b border-[var(--odoo-border)]/60">
                      <td className="py-1">{r.row_index}</td>
                      <td className="py-1 font-mono">{r.match_value}</td>
                      <td className="py-1 font-mono">{r.filename}</td>
                      <td className="py-1">{r.ok ? "yes" : "no"}</td>
                      <td className="py-1 text-[var(--odoo-danger)]">{r.error ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="odoo-sheet mt-6 space-y-4 p-4" data-testid="image-import-panel">
          <h2 className="text-sm font-semibold text-[var(--odoo-primary)]">Bulk image import</h2>
          <p className="text-xs text-[var(--odoo-muted)]">
            CSV manifest (<code>match,name,filename</code>) + ZIP of images → writes base64 to an
            image/binary field. Images are downscaled server-side (max {1920}px, 5MB guard).
          </p>
          <div className="flex flex-wrap gap-2">
            <label className="text-xs">
              Manifest CSV
              <input
                type="file"
                accept=".csv,.txt"
                className="mt-1 block text-sm"
                onChange={(e) => setImgManifest(e.target.files?.[0] ?? null)}
              />
            </label>
            <label className="text-xs">
              Images ZIP
              <input
                type="file"
                accept=".zip"
                className="mt-1 block text-sm"
                onChange={(e) => setImgZip(e.target.files?.[0] ?? null)}
              />
            </label>
            <button
              type="button"
              disabled={busy || !imgManifest || !imgZip}
              onClick={() => void onImagePreview()}
              className="self-end border border-[var(--odoo-primary)] px-3 py-1.5 text-sm text-[var(--odoo-primary)] disabled:opacity-50"
            >
              Preview manifest
            </button>
          </div>
          {imgPreview && (
            <>
              <div className="grid gap-2 sm:grid-cols-2 text-sm">
                <label>
                  Match field
                  <input
                    value={imgMatchField}
                    onChange={(e) => setImgMatchField(e.target.value)}
                    className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
                  />
                </label>
                <label>
                  Image field
                  <input
                    value={imgField}
                    onChange={(e) => setImgField(e.target.value)}
                    placeholder={imgPreview.image_field}
                    className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
                  />
                </label>
              </div>
              <pre className="max-h-32 overflow-auto bg-[#f8f9fa] p-2 text-xs text-[#1f1f1f]">
                {JSON.stringify(imgPreview.sample_rows, null, 2)}
              </pre>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void runImageCommit(true)}
                  className="border border-[var(--odoo-primary)] px-3 py-1.5 text-sm text-[var(--odoo-primary)] disabled:opacity-50"
                >
                  Dry-run images
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setImgConfirmOpen(true)}
                  className="bg-[var(--odoo-danger)] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Commit image writes
                </button>
              </div>
            </>
          )}
          {imgResult && (
            <div className="overflow-x-auto text-sm" data-testid="image-import-results">
              <p>
                updated={imgResult.updated} failed={imgResult.failed} skipped={imgResult.skipped}
              </p>
              <table className="mt-2 w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[var(--odoo-border)]">
                    <th className="py-1">#</th>
                    <th className="py-1">match</th>
                    <th className="py-1">file</th>
                    <th className="py-1">ok</th>
                    <th className="py-1">error</th>
                  </tr>
                </thead>
                <tbody>
                  {imgResult.results.map((r) => (
                    <tr key={r.row_index} className="border-b border-[var(--odoo-border)]/60">
                      <td className="py-1">{r.row_index}</td>
                      <td className="py-1 font-mono">{r.match_value}</td>
                      <td className="py-1 font-mono">{r.filename}</td>
                      <td className="py-1">{r.ok ? "yes" : "no"}</td>
                      <td className="py-1 text-[var(--odoo-danger)]">{r.error ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Commit bulk import"
        warning={`Write ${rows.length} row(s) to ${model} on this live Odoo connection.`}
        risks={[
          "Creates or updates business records",
          "Wrong Many2one mapping can link incorrect relations",
          "Partial success is not auto-rolled back",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => void runCommit(false, phrase)}
      />
      <ConfirmDialog
        open={imgConfirmOpen}
        title="Commit bulk image import"
        warning={`Write images to ${model} on this live Odoo connection.`}
        risks={[
          "Overwrites binary/image data on matched records",
          "Wrong match field can attach images to incorrect records",
          "Partial success is not auto-rolled back",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setImgConfirmOpen(false)}
        onConfirm={(phrase) => void runImageCommit(false, phrase)}
      />
    </main>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import {
  api,
  ConfirmationRequiredError,
  type Connection,
  type ScanFindOut,
} from "@/lib/api";
import { BarcodeScanner } from "@/components/scanner/BarcodeScanner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { connectionSupports } from "@/lib/capabilities";

const CONFIRM_PHRASE = "I understand the risks";

export function ScanToFieldPanel({
  connectionId,
  connection,
  defaultModel,
}: {
  connectionId: string;
  connection: Connection | null;
  defaultModel?: string;
}) {
  const [mode, setMode] = useState<"find" | "write">("find");
  const [model, setModel] = useState(defaultModel ?? "x_lib_book");
  const [field, setField] = useState("x_barcode");
  const [recordId, setRecordId] = useState("");
  const [lastScan, setLastScan] = useState("");
  const [findResult, setFindResult] = useState<ScanFindOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const moduleWidgetAllowed = connectionSupports(connection, "barcode_scan_module");

  async function onScan(value: string) {
    setLastScan(value);
    setError(null);
    setNotice(null);
    if (mode === "find") {
      setBusy(true);
      try {
        const res = await api.bulkScanFind(connectionId, { model, field, value });
        setFindResult(res);
        setNotice(res.count === 1 ? `Found record #${res.records[0]?.id}` : `Found ${res.count} record(s)`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Scan find failed");
      } finally {
        setBusy(false);
      }
      return;
    }
    if (!recordId.trim()) {
      setError("Record id required for single-record write mode");
      return;
    }
    setConfirmOpen(true);
  }

  async function runWrite(phrase?: string) {
    if (!lastScan || !recordId.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkMassEdit(connectionId, {
        model,
        ids: [Number(recordId)],
        values: { [field]: lastScan },
        dry_run: false,
        confirm_advanced: true,
        confirm_phrase: phrase || CONFIRM_PHRASE,
      });
      setNotice(`Updated record ${recordId}: ${res.message}`);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Write failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-8 border border-[#E5E5E5] bg-white p-6">
      <h2 className="text-lg font-semibold text-[#212529]">Scan to field (§16)</h2>
      <p className="mt-1 text-sm text-[#6C757D]">
        In-app camera scanner (all tiers). Exported OWL widget module is available on Odoo.sh /
        self-host only — not native Odoo.
      </p>

      {!moduleWidgetAllowed && (
        <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          Exported <code className="text-xs">x_barcode_scan</code> widget module is hidden on Odoo
          Online — use this in-app scanner or deploy to Odoo.sh/on-prem.
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2">
          <input type="radio" checked={mode === "find"} onChange={() => setMode("find")} />
          Bulk: scan → find record
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" checked={mode === "write"} onChange={() => setMode("write")} />
          Single record: scan → write field
        </label>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <label className="block text-sm">
          Model
          <input className="mt-1 w-full border px-3 py-2 text-sm" value={model} onChange={(e) => setModel(e.target.value)} />
        </label>
        <label className="block text-sm">
          Field
          <input className="mt-1 w-full border px-3 py-2 text-sm" value={field} onChange={(e) => setField(e.target.value)} />
        </label>
        {mode === "write" && (
          <label className="block text-sm">
            Record id
            <input className="mt-1 w-full border px-3 py-2 text-sm" value={recordId} onChange={(e) => setRecordId(e.target.value)} />
          </label>
        )}
      </div>

      <div className="mt-4">
        <BarcodeScanner onScan={onScan} onError={setError} />
      </div>

      {lastScan && (
        <p className="mt-2 text-sm">
          Last scan: <code>{lastScan}</code>
        </p>
      )}

      {findResult && findResult.count > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {findResult.records.map((r) => (
            <li key={r.id}>
              #{r.id} {r.display_name ?? ""}
              {connection?.url && (
                <>
                  {" "}
                  <Link
                    className="text-[#714B67] underline"
                    href={`${connection.url}/web#id=${r.id}&model=${model}&view_type=form`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open in Odoo
                  </Link>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {moduleWidgetAllowed && (
        <p className="mt-4 text-xs text-[#6C757D]">
          Module export: enable <code>include_barcode_scan_widget</code> in ModuleSpec to emit{" "}
          <code>widget=&quot;x_barcode_scan&quot;</code> assets (LGPL-3 + Apache-2 ZXing attribution in README).
        </p>
      )}

      {notice && <p className="mt-3 text-sm text-green-700">{notice}</p>}
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      {busy && <p className="mt-2 text-xs text-[#6C757D]">Working…</p>}

      <ConfirmDialog
        open={confirmOpen}
        title="Scan write to field"
        warning={error ?? `Write scanned value to ${model}/${recordId}.${field}`}
        risks={["Live RPC write on Odoo", "Mass-edit policy applies"]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => void runWrite(phrase)}
      />
    </section>
  );
}

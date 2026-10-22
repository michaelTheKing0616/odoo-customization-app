"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { Placement } from "@/lib/api/view-engine-2b";
import type { BrandCompany, EmailChecksOut, FromDocOut } from "@/lib/api/view-engine-2c";
import type { BrandPreset } from "@/lib/api/view-engine-2d";
import { Note } from "../view-designer/Note";
import styles from "./ReportDesigner.module.css";
import { noteWriteRefusal } from "../view-designer/writeModeSignal";

const msg = (e: unknown, fallback: string) => {
  noteWriteRefusal(e);
  return e instanceof Error ? e.message : fallback;
};

/** Each company keeps its own document style; copy one company's style to others. */
export function CompanyBrands({ connectionId }: { connectionId: string }) {
  const [rows, setRows] = useState<BrandCompany[] | null>(null);
  const [from, setFrom] = useState<number | null>(null);
  const [to, setTo] = useState<number[]>([]);
  const load = () => api.brandCompanies(connectionId).then((o) => setRows(o.companies)).catch((e) => toast.error(msg(e, "Couldn't load companies.")));
  if (!rows) return <Button size="sm" variant="ghost" onClick={() => void load()}>Branding per company…</Button>;
  return (
    <div className={styles.stack} data-testid="rd2c-companies">
      <h2 className={styles.title}>Branding per company</h2>
      <ul className={styles.stack}>
        {rows.map((c) => (
          <li key={c.id} className={styles.small}>
            <label>
              <input type="radio" name="brand-from" checked={from === c.id} onChange={() => setFrom(c.id)} /> Copy from
            </label>{" "}
            <label>
              <input type="checkbox" checked={to.includes(c.id)} disabled={from === c.id} onChange={(e) => setTo((x) => (e.target.checked ? [...x, c.id] : x.filter((y) => y !== c.id)))} /> to
            </label>{" "}
            <strong>{c.name}</strong>{" "}
            {c.primary_color ? <span aria-label={`Main colour ${c.primary_color}`} className={styles.swatch} style={{ background: String(c.primary_color) }} /> : null}{" "}
            {c.font ? String(c.font) : "No font set"}{c.external_report_layout_id ? `, ${c.external_report_layout_id[1]}` : ""}
            {c.can_undo ? (
              <Button size="sm" variant="ghost" onClick={() => api.brandUndo(connectionId, {}, c.id).then(() => { toast.success(`Branding put back for ${c.name}`); void load(); }).catch((e) => toast.error(msg(e, "Couldn't undo.")))}>Undo</Button>
            ) : null}
          </li>
        ))}
      </ul>
      <Button size="sm" variant="primary" disabled={!from || !to.length} onClick={async () => {
        if (!from) return;
        try {
          const out = await api.brandCopy(connectionId, from, to);
          const bad = out.results.filter((r) => !r.ok);
          if (bad.length) toast.error(`${bad.length} compan${bad.length === 1 ? "y" : "ies"} kept their style: ${bad[0].error}`);
          else toast.success(`Style copied to ${out.results.length} compan${out.results.length === 1 ? "y" : "ies"}`);
          setTo([]);
          void load();
        } catch (e) {
          toast.error(msg(e, "Couldn't copy the style."));
        }
      }}>Copy the style</Button>
      <BrandPresets connectionId={connectionId} companies={rows} />
    </div>
  );
}

/** Save a company's style as a preset and reuse it in any database. */
function BrandPresets({ connectionId, companies }: { connectionId: string; companies: BrandCompany[] }) {
  const [presets, setPresets] = useState<BrandPreset[]>([]);
  const [name, setName] = useState("");
  const [company, setCompany] = useState<number>(companies[0]?.id ?? 0);
  const load = () => api.presets(connectionId).then((o) => setPresets(o.presets)).catch(() => undefined);
  useEffect(() => { void load(); }, [connectionId]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className={styles.stack} data-testid="rd2d-presets">
      <h3 className={styles.title}>Style presets (shared by all your databases)</h3>
      <label className={styles.small}>
        Company{" "}
        <select value={company} onChange={(e) => setCompany(Number(e.target.value))}>
          {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      <div className={styles.small}>
        <input aria-label="Preset name" placeholder="Preset name" value={name} onChange={(e) => setName(e.target.value)} />{" "}
        <Button size="sm" variant="ghost" disabled={!name.trim() || !company}
          onClick={() => api.presetSave(connectionId, company, name.trim()).then(() => { setName(""); toast.success("Preset saved"); void load(); }).catch((e) => toast.error(msg(e, "Couldn't save.")))}>
          Save this company&apos;s style
        </Button>
      </div>
      <ul className={styles.stack}>
        {presets.map((pr) => (
          <li key={pr.id} className={styles.small}>
            <strong>{pr.name}</strong> {pr.payload.font ?? ""} {pr.payload.primary_color ?? ""}{" "}
            <Button size="sm" variant="ghost"
              onClick={() => api.presetApply(connectionId, pr.id, company).then((o) => { toast.success("Preset applied"); o.skipped.forEach((x) => toast(x)); }).catch((e) => toast.error(msg(e, "Couldn't apply.")))}>
              Apply to company
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Upload a sample document; Ingenium drafts matching blocks using only fields that exist. */
export function FromDocument({ connectionId, reportId, onDraft }: { connectionId: string; reportId: number; onDraft: (p: Placement[]) => void }) {
  const [out, setOut] = useState<FromDocOut | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className={styles.stack} data-testid="rd2c-fromdoc">
      <label className={styles.small}>
        Start from a sample document (PDF or photo)
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.webp,.txt"
          disabled={busy}
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            if (file.size > 10 * 1024 * 1024) { toast.error("Files up to 10 MB."); return; }
            setBusy(true);
            try {
              const b64 = await new Promise<string>((resolve, reject) => {
                const r = new FileReader();
                r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
                r.onerror = () => reject(new Error("The file couldn't be read."));
                r.readAsDataURL(file);
              });
              const res = await api.reportFromDocument(connectionId, reportId, file.name, b64);
              setOut(res);
              if (res.placements.length) {
                onDraft(res.placements);
                toast.success("Draft made from the document. Check it, then publish when ready.");
              }
            } catch (err) {
              toast.error(msg(err, "The document couldn't be read."));
            } finally {
              setBusy(false);
            }
          }}
        />
      </label>
      {busy ? <Note tone="busy" role="status">Reading the document…</Note> : null}
      {out ? (
        <div className={styles.small}>
          {out.unclear.map((u) => <p key={u}>{u}</p>)}
          {out.dropped.length ? <p>Left out (no matching field in this database): {out.dropped.slice(0, 8).join("; ")}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

/** How common email apps will treat this email, plus a dark-mode preview. */
export function EmailAppChecks({ connectionId, templateId, recordId, html }: { connectionId: string; templateId: number; recordId: number | null; html: string | null }) {
  const [out, setOut] = useState<EmailChecksOut | null>(null);
  const [dark, setDark] = useState(false);
  const [to, setTo] = useState("");
  return (
    <div className={styles.stack} data-testid="em2c-checks">
      <div className={styles.small}>
        <Button size="sm" variant="ghost" onClick={() => api.emailAppChecks(connectionId, templateId, recordId).then(setOut).catch((e) => toast.error(msg(e, "Couldn't check.")))}>
          Check in email apps
        </Button>
        {html ? (
          <Button size="sm" variant="ghost" aria-pressed={dark} onClick={() => setDark(!dark)}>{dark ? "Light preview" : "Dark mode preview"}</Button>
        ) : null}
      </div>
      {out ? (
        <div className={styles.stack}>
          <Note tone="info" role="status">{out.summary} <span>({out.size_kb} KB, {out.checked})</span></Note>
          <ul className={styles.stack}>
            {out.findings.map((f, i) => (
              <li key={i} className={styles.small} data-severity={f.severity}>
                <strong>{f.apps}:</strong> {f.text} <em>{f.fix}</em>
              </li>
            ))}
          </ul>
          <p className={styles.small}>{out.note}</p>
        </div>
      ) : null}
      {recordId ? (
        <div className={styles.small}>
          <input aria-label="Send a test to" placeholder="you@example.com" value={to} onChange={(e) => setTo(e.target.value)} />{" "}
          <Button size="sm" variant="ghost" disabled={!to.includes("@")}
            onClick={() => api.emailTestSend(connectionId, templateId, recordId, to).then((o) => (o.status === "sent" || o.status === "queued" ? toast.success(`Test sent to ${o.to}`) : toast.error(o.note))).catch((e) => toast.error(msg(e, "Couldn't send.")))}>
            Send a test to this address
          </Button>
          <span> Only this address gets it. Sent through this Odoo&apos;s mail server.</span>
        </div>
      ) : null}
      {dark && html ? (
        <iframe title="Email in dark mode" srcDoc={html} sandbox="" className={styles.emailDark} style={{ width: 600, maxWidth: "100%", minHeight: 360 }} />
      ) : null}
    </div>
  );
}

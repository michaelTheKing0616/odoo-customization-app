"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Sheet } from "@/components/ui/Sheet";
import { api } from "@/lib/api";
import type { EngineViewType } from "@/lib/api/view-engine";
import type { GuardOut, LayoutPackage, PackageCheckOut, ScreenItem, ScreenTemplate, TranslationsOut } from "@/lib/api/view-engine-2b";
import { downloadJson, errorDetail } from "@/lib/viewDesigner2b";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";

export type BuilderTab = "screen" | "translate" | "guard" | "package";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tab: BuilderTab;
  onTab: (t: BuilderTab) => void;
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  viewId: number | null;
  layerHash: string | null;
  onOpenScreen: (viewType: EngineViewType, viewId: number | null) => void;
  onChanged: () => void;
  errorText: (err: unknown) => string;
};

const TABS: Array<[BuilderTab, string]> = [["screen", "New screen"], ["translate", "Translations"], ["guard", "Upgrade check"], ["package", "Move to production"]];

/** Screen-level tools: new screens, translations, upgrade guard, staging → production package. */
export function BuilderSheet(p: Props) {
  return (
    <Sheet open={p.open} onOpenChange={p.onOpenChange} title="Screen tools" description={`${p.model}, ${p.viewType}`}>
      <div role="tablist" className={styles.panelTabs}>
        {TABS.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={p.tab === id} onClick={() => p.onTab(id)}>{label}</button>
        ))}
      </div>
      <div className={styles.panelBody}>
        {p.tab === "screen" ? <NewScreen {...p} /> : null}
        {p.tab === "translate" ? <Translations {...p} /> : null}
        {p.tab === "guard" ? <Guard {...p} /> : null}
        {p.tab === "package" ? <PackageTab {...p} /> : null}
      </div>
    </Sheet>
  );
}

function NewScreen({ connectionId, model, onOpenScreen, errorText }: Props) {
  const [templates, setTemplates] = useState<ScreenTemplate[]>([]);
  const [screens, setScreens] = useState<ScreenItem[]>([]);
  const [pick, setPick] = useState("form|two_columns");
  const [label, setLabel] = useState("");
  const [menu, setMenu] = useState(true);
  const [busy, setBusy] = useState(false);
  const load = () =>
    api.screenTemplates(connectionId, model).then((o) => { setTemplates(o.templates); setScreens(o.screens); }).catch((e) => toast.error(errorText(e)));
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId, model]);
  const [vt, template] = pick.split("|") as [EngineViewType, string];
  return (
    <div className={styles.stack} data-testid="vd-new-screen">
      <p className={styles.muted}>A new screen of its own. Odoo&apos;s default screen is not changed.</p>
      <ul className={styles.fieldList} role="radiogroup" aria-label="Start from">
        {templates.map((t) => (
          <li key={`${t.view_type}|${t.key}`}>
            <label className={styles.check}>
              <input type="radio" name="tpl" disabled={!t.available} checked={pick === `${t.view_type}|${t.key}`} onChange={() => setPick(`${t.view_type}|${t.key}`)} />
              {t.view_type}: {t.label} {t.reason ? <span className={styles.muted}>({t.reason})</span> : null}
            </label>
          </li>
        ))}
      </ul>
      <label className={styles.fieldLabel}>
        Name
        <Input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} />
      </label>
      {vt !== "search" ? (
        <label className={styles.check}>
          <input type="checkbox" checked={menu} onChange={(e) => setMenu(e.target.checked)} /> Add a menu item that opens it
        </label>
      ) : null}
      <Button
        variant="primary"
        size="sm"
        loading={busy}
        disabled={!label.trim()}
        onClick={async () => {
          setBusy(true);
          try {
            const out = await api.screenCreate(connectionId, { model, view_type: vt, template, label: label.trim(), make_menu: menu && vt !== "search" });
            toast.success("Screen created in Odoo");
            setLabel("");
            await load();
            onOpenScreen(out.view_type, out.view_id);
          } catch (err) {
            toast.error(errorText(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        Create screen
      </Button>
      {screens.length ? (
        <>
          <h3 className={styles.sectionTitle}>Screens made here</h3>
          <ul className={styles.fieldList}>
            {screens.map((s) => (
              <li key={s.id} className={styles.fieldRow}>
                <span>{s.name} <span className={styles.muted}>{s.payload.view_type}{s.exists ? "" : " (removed in Odoo)"}</span></span>
                <span>
                  {s.exists ? <Button size="sm" variant="ghost" onClick={() => onOpenScreen(s.payload.view_type, s.payload.view_id)}>Open</Button> : null}
                  <Button size="sm" variant="ghost" onClick={async () => {
                    if (!window.confirm(`Remove “${s.name}”, its menu item and its changes from Odoo?`)) return;
                    try {
                      await api.screenDelete(connectionId, s.id);
                      await load();
                      onOpenScreen(s.payload.view_type, null);
                    } catch (err) {
                      toast.error(errorText(err));
                    }
                  }}>Remove</Button>
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

function Translations({ connectionId, model, viewType, viewId, layerHash, onChanged, errorText }: Props) {
  const [data, setData] = useState<TranslationsOut | null>(null);
  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const screen = { model, view_type: viewType, view_id: viewId };
  const load = () => api.translations(connectionId, screen).then(setData).catch((e) => toast.error(errorText(e)));
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId, model, viewType, viewId]);
  if (!data) return <p className={styles.muted}>Loading labels in every language…</p>;
  if (data.hint) return <Note tone="warning">{data.hint}</Note>;
  return (
    <table className={styles.table} data-testid="vd-translations">
      <thead>
        <tr><th>English</th>{data.languages.map((l) => <th key={l.code}>{l.name}</th>)}<th /></tr>
      </thead>
      <tbody>
        {data.rows.map((r) => (
          <tr key={r.node}>
            <td>{r.en}</td>
            {data.languages.map((l) => (
              <td key={l.code}>
                <Input aria-label={`${r.en} in ${l.name}`} defaultValue={r.langs[l.code] ?? ""} maxLength={80}
                  onChange={(e) => setDraft((d) => ({ ...d, [r.node]: { ...(d[r.node] ?? {}), [l.code]: e.target.value } }))} />
              </td>
            ))}
            <td>
              <Button size="sm" variant="ghost" loading={saving === r.node} disabled={!draft[r.node]} onClick={async () => {
                setSaving(r.node);
                try {
                  await api.translationSave(connectionId, screen, r.node, draft[r.node], layerHash);
                  toast.success(`Saved translations of “${r.en}”`);
                  setDraft((d) => { const n = { ...d }; delete n[r.node]; return n; });
                  onChanged();
                  await load();
                } catch (err) {
                  toast.error(errorText(err));
                } finally {
                  setSaving(null);
                }
              }}>Save</Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Guard({ connectionId, model, viewType, viewId, onChanged, errorText }: Props) {
  const [data, setData] = useState<GuardOut | null>(null);
  const [fixing, setFixing] = useState(false);
  const screen = { model, view_type: viewType, view_id: viewId };
  const load = () => api.guardCheck(connectionId, screen).then(setData).catch((e) => toast.error(errorText(e)));
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId, model, viewType, viewId]);
  if (!data) return <p className={styles.muted}>Checking your changes against Odoo…</p>;
  if (!data.has_layer) return <p className={styles.muted}>This screen has no Ingenium changes to check.{data.problem ? ` ${data.problem}` : ""}</p>;
  return (
    <div className={styles.stack} data-testid="vd-guard">
      <p className={data.ok ? styles.ok : styles.notice}>{data.summary}</p>
      {data.odoo_changed ? <p className={styles.muted}>Odoo&apos;s own screens changed since your last publish (an update or a new app).</p> : null}
      <ul className={styles.fieldList}>
        {(data.steps ?? []).map((s) => (
          <li key={s.index} className={styles.listItem}>
            <span>{s.status === "ok" ? "✓" : "⚠"} {s.text}</span>
            {s.reason ? <span className={styles.muted}> {s.reason}</span> : null}
          </li>
        ))}
      </ul>
      {!data.ok ? (
        <Button size="sm" variant="primary" loading={fixing} onClick={async () => {
          setFixing(true);
          try {
            const out = await api.guardFix(connectionId, screen);
            toast.success(out.changed ? `Fixed. ${out.dropped.length ? `Removed ${out.dropped.length} change(s) that no longer apply.` : ""}` : out.message ?? "Nothing needed fixing.");
            onChanged();
            await load();
          } catch (err) {
            toast.error(errorText(err));
          } finally {
            setFixing(false);
          }
        }}>Fix: keep what still works</Button>
      ) : null}
    </div>
  );
}

function PackageTab({ connectionId, model, viewType, viewId, onChanged, errorText }: Props) {
  const [pkg, setPkg] = useState<LayoutPackage | null>(null);
  const [check, setCheck] = useState<PackageCheckOut | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className={styles.stack} data-testid="vd-package">
      <h3 className={styles.sectionTitle}>Export from this database</h3>
      <p className={styles.muted}>Saves this screen&apos;s published changes and the custom fields they use as a file.</p>
      <Button size="sm" onClick={async () => {
        try {
          const out = await api.packageExport(connectionId, { model, view_type: viewType, view_id: viewId });
          downloadJson(out.file_name, out.package);
        } catch (err) {
          toast.error(errorText(err));
        }
      }}>Download package</Button>

      <h3 className={styles.sectionTitle}>Import into this database</h3>
      <input type="file" accept="application/json,.json" aria-label="Package file" onChange={async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        try {
          const parsed = JSON.parse(await file.text()) as LayoutPackage;
          setPkg(parsed);
          setCheck(await api.packageCheck(connectionId, parsed));
        } catch (err) {
          setPkg(null);
          setCheck(null);
          toast.error(err instanceof SyntaxError ? "That file isn't a package." : errorText(err));
        }
      }} />
      {check ? (
        <div className={styles.proposal}>
          <p>{check.model}, {check.view_type}, {check.steps} changes, from Odoo {check.from_major} to Odoo {check.to_major}</p>
          {check.fields_to_create.length ? <p>Will create fields: {check.fields_to_create.map((f) => f.field_description ?? f.name).join(", ")}</p> : null}
          {check.has_changes_here ? <Note tone="warning">This screen already has Ingenium changes here. Importing replaces them.</Note> : null}
          {check.problems.length ? <ul className={styles.notice}>{check.problems.map((x) => <li key={x}>{x}</li>)}</ul> : null}
          <Button size="sm" variant="primary" loading={busy} disabled={!check.ok || !pkg} onClick={async () => {
            if (!pkg) return;
            setBusy(true);
            try {
              const out = await api.packageImport(connectionId, pkg, check.has_changes_here);
              toast.success(`Imported. ${out.fields_created.length ? `Created ${out.fields_created.length} field(s).` : ""}`);
              onChanged();
            } catch (err) {
              const d = errorDetail(err);
              toast.error(errorText(err), { description: Array.isArray(d?.problems) ? (d.problems as string[]).join(" ") : undefined });
            } finally {
              setBusy(false);
            }
          }}>Import</Button>
        </div>
      ) : null}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Sheet } from "@/components/ui/Sheet";
import { api } from "@/lib/api";
import type { EngineOp, EngineRecord, EngineViewType, Role } from "@/lib/api/view-engine";
import type {
  A11yOut,
  ABResults,
  ApprovalPayload,
  DashOptions,
  DashPreview,
  DashSpec,
  DigestOut,
  Heat,
  Item2c,
  RoleDiff,
  RoleLayer,
  SaveBlockersOut,
  SchedulePayload,
  StarterOption,
  StepSection,
  TourStep,
  WatchPayload,
} from "@/lib/api/view-engine-2c";
import { Insights2d, Publishing2d, Tiles2d } from "./Builder2d";
import { Note } from "../view-designer/Note";
import { errorDetail } from "@/lib/viewDesigner2b";
import styles from "./ViewDesigner.module.css";

export type Tab2c = "insights" | "roles" | "dashboards" | "starters" | "publishing";
const TABS: Array<[Tab2c, string]> = [["insights", "Insights"], ["roles", "Roles"], ["dashboards", "Dashboards"], ["starters", "Starter screens"], ["publishing", "Publishing"]];

export type Props2c = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tab: Tab2c;
  onTab: (t: Tab2c) => void;
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  viewId: number | null;
  ops: EngineOp[];
  summary: string[];
  layerHash: string | null;
  roles: Role[];
  fields: Record<string, { string?: string; type?: string }>;
  heatOn: boolean;
  onHeat: (heat: Record<string, Heat> | null) => void;
  sampleOn: boolean;
  onSample: (rec: EngineRecord | null) => void;
  simulate: string;
  onSimulate: (key: string) => void;
  onTour: (steps: TourStep[]) => void;
  onJump: (nodeId: string) => void;
  onOpenScreen: (viewType: EngineViewType, viewId: number | null) => void;
  onClearOps: () => void;
  onChanged: () => void;
  errorText: (err: unknown) => string;
  selectedNode?: string | null;
  onAddOps?: (ops: EngineOp[], label: string) => void;
};

/** Stage 2c tools: insights, role layouts, dashboards, starters and safe publishing. */
export function Builder2cSheet(p: Props2c) {
  return (
    <Sheet open={p.open} onOpenChange={p.onOpenChange} title="Screen insights and publishing" description={`${p.model}, ${p.viewType}`}>
      <div role="tablist" className={styles.panelTabs}>
        {TABS.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={p.tab === id} onClick={() => p.onTab(id)}>{label}</button>
        ))}
      </div>
      <div className={styles.panelBody}>
        {p.tab === "insights" ? <><InsightsTab {...p} /><Insights2d {...p} /></> : null}
        {p.tab === "roles" ? <RolesTab {...p} /> : null}
        {p.tab === "dashboards" ? <><DashboardsTab {...p} /><Tiles2d {...p} /></> : null}
        {p.tab === "starters" ? <StartersTab {...p} /> : null}
        {p.tab === "publishing" ? <><PublishingTab {...p} /><Publishing2d {...p} /></> : null}
      </div>
    </Sheet>
  );
}

const screenOf = (p: Props2c) => ({ model: p.model, view_type: p.viewType, view_id: p.viewId, ops: p.ops });

// ---------------------------------------------------------------- Insights

function InsightsTab(p: Props2c) {
  const [blockers, setBlockers] = useState<SaveBlockersOut | null>(null);
  const [a11y, setA11y] = useState<A11yOut | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const run = async <T,>(key: string, fn: () => Promise<T>, done: (v: T) => void) => {
    setBusy(key);
    try {
      done(await fn());
    } catch (err) {
      toast.error(p.errorText(err));
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className={styles.stack} data-testid="vd2c-insights">
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>Explain this screen</h3>
        <p className={styles.muted}>A short guided tour, written by Ingenium from the screen itself.</p>
        <Button size="sm" variant="ghost" loading={busy === "tour"} onClick={() => void run("tour", () => api.explainScreen(p.connectionId, screenOf(p)), (o) => { p.onTour(o.steps); p.onOpenChange(false); })}>
          Start the tour
        </Button>
      </section>
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>Usage heatmap</h3>
        <p className={styles.muted}>Colours each field by how often it&apos;s filled in and changed. Counts only.</p>
        <Button
          size="sm"
          variant="ghost"
          aria-pressed={p.heatOn}
          loading={busy === "heat"}
          onClick={() => (p.heatOn ? p.onHeat(null) : void run("heat", () => api.heatmap(p.connectionId, screenOf(p)), (o) => { p.onHeat(o.heat); toast(o.note); }))}
        >
          {p.heatOn ? "Hide heatmap" : "Show heatmap"}
        </Button>
      </section>
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>Sample data</h3>
        <p className={styles.muted}>Fill the preview with made-up values, clearly marked as samples. Nothing is saved.</p>
        <Button
          size="sm"
          variant="ghost"
          aria-pressed={p.sampleOn}
          loading={busy === "sample"}
          onClick={() => (p.sampleOn ? p.onSample(null) : void run("sample", () => api.sampleData(p.connectionId, screenOf(p), 1), (o) => p.onSample(o.records[0] as unknown as EngineRecord)))}
        >
          {p.sampleOn ? "Back to real records" : "Use sample data"}
        </Button>
      </section>
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>What blocks saving</h3>
        <Button size="sm" variant="ghost" loading={busy === "block"} onClick={() => void run("block", () => api.saveBlockers(p.connectionId, screenOf(p)), setBlockers)}>
          Check each stage
        </Button>
        {blockers ? (
          <div className={styles.stack} data-testid="vd2c-blockers">
            <Note tone="info" role="status">{blockers.summary}</Note>
            <ul className={styles.list}>
              {blockers.stages.map((st) => (
                <li key={String(st.value)}>
                  <details>
                    <summary>
                      {st.label}: {st.always.length + st.at_stage.length} must be filled{st.depends.length ? `, ${st.depends.length} depend on other values` : ""}
                    </summary>
                    <ul className={styles.list}>
                      {[...st.always, ...st.at_stage, ...st.depends].map((b) => (
                        <li key={`${st.value}-${b.field}`} className={styles.listItem}>
                          <span>
                            {b.label} <span className={styles.muted}>{b.why}{typeof b.missing_now === "number" && b.missing_now > 0 ? ` ${b.missing_now} records here are missing it now.` : ""}</span>
                          </span>
                          <Button size="sm" variant="ghost" onClick={() => { p.onJump(b.node); p.onOpenChange(false); }}>Show</Button>
                        </li>
                      ))}
                    </ul>
                  </details>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>Accessibility</h3>
        <label className={styles.fieldLabel}>
          See the screen as
          <select className={styles.select} value={p.simulate} onChange={(e) => p.onSimulate(e.target.value)} data-testid="vd2c-simulate">
            <option value="">Normal vision</option>
            {(a11y?.simulations ?? DEFAULT_SIMS).map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </label>
        <Button size="sm" variant="ghost" loading={busy === "a11y"} onClick={() => void run("a11y", () => api.a11y(p.connectionId, screenOf(p)), setA11y)}>
          Check for screen readers and keyboards
        </Button>
        {a11y ? (
          <div className={styles.stack} data-testid="vd2c-a11y">
            <Note tone="info" role="status">{a11y.summary}</Note>
            <ul className={styles.list}>
              {a11y.issues.map((i, n) => (
                <li key={`${i.node}-${n}`} className={styles.listItem}>
                  <span>{i.text}{i.detail ? <span className={styles.muted}> {i.detail}</span> : null}</span>
                  <Button size="sm" variant="ghost" onClick={() => { p.onJump(i.node); p.onOpenChange(false); }}>Show</Button>
                </li>
              ))}
            </ul>
            <details>
              <summary>What a screen reader says, in order ({a11y.reading_order.length})</summary>
              <ol className={styles.list}>
                {a11y.reading_order.slice(0, 80).map((o, n) => <li key={`${o.node}-${n}`}>{o.say}</li>)}
              </ol>
            </details>
          </div>
        ) : null}
      </section>
    </div>
  );
}

const DEFAULT_SIMS = [
  { key: "protanopia", label: "Red-blind" },
  { key: "deuteranopia", label: "Green-blind" },
  { key: "tritanopia", label: "Blue-blind" },
  { key: "achromatopsia", label: "No colour" },
  { key: "low_vision", label: "Blurred vision" },
  { key: "zoom200", label: "Zoomed to 200%" },
];

// ---------------------------------------------------------------- Roles

function RolesTab(p: Props2c) {
  const [sections, setSections] = useState<StepSection[]>([]);
  const [existing, setExisting] = useState<RoleLayer[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [role, setRole] = useState("");
  const [roleA, setRoleA] = useState("");
  const [roleB, setRoleB] = useState("");
  const [diff, setDiff] = useState<RoleDiff | null>(null);
  const askApproval = (err: unknown, action: "abtest_start" | "abtest_stop", payload: Record<string, unknown>, what: string) => {
    if (!errorDetail(err)?.needs_approval) {
      toast.error(p.errorText(err));
      return;
    }
    toast.error(p.errorText(err), {
      duration: 15000,
      action: { label: "Ask for approval", onClick: () => void api.requestAction(p.connectionId, action, payload, [what]).then(() => toast.success("Sent for approval")).catch((e) => toast.error(p.errorText(e))) },
    });
  };
  const [tests, setTests] = useState<Item2c<{ status: string; role_b_name: string; metric_label: string; started_at: string }>[]>([]);
  const [results, setResults] = useState<Record<string, ABResults>>({});
  const [metric, setMetric] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(true);
  const isForm = p.viewType === "form";
  const load = () => {
    if (isForm) api.stepsOptions(p.connectionId, screenOf(p)).then((o) => { setSections(o.sections); setExisting(o.existing); }).catch(() => undefined);
    api.abList(p.connectionId, p.model).then((o) => setTests(o.tests)).catch(() => undefined);
  };
  useEffect(load, [p.connectionId, p.model, p.viewType, p.viewId]); // eslint-disable-line react-hooks/exhaustive-deps
  const roleSelect = (value: string, set: (v: string) => void, label: string) => (
    <select className={styles.select} aria-label={label} value={value} onChange={(e) => set(e.target.value)}>
      <option value="">Pick a role…</option>
      {p.roles.map((r) => <option key={r.xmlid} value={r.xmlid}>{r.name} ({r.people})</option>)}
    </select>
  );
  const fieldChoices = Object.entries(p.fields).filter(([, m]) => m.type && !["one2many", "binary"].includes(m.type)).sort((a, b) => String(a[1].string).localeCompare(String(b[1].string)));
  return (
    <div className={styles.stack} data-testid="vd2c-roles">
      {isForm ? (
        <section className={styles.stack}>
          <h3 className={styles.sectionTitle}>Step-by-step mode</h3>
          <p className={styles.muted}>Turns sections into numbered steps for one role. Everyone else keeps the normal screen.</p>
          {roleSelect(role, setRole, "Role for steps")}
          <ul className={styles.list}>
            {sections.map((s) => (
              <li key={s.node}>
                <label className={styles.check}>
                  <input type="checkbox" checked={picked.includes(s.node)} onChange={(e) => setPicked((x) => (e.target.checked ? [...x, s.node] : x.filter((y) => y !== s.node)))} />
                  {picked.includes(s.node) ? `Step ${picked.indexOf(s.node) + 1}: ` : ""}{s.label} <span className={styles.muted}>({s.fields} fields)</span>
                </label>
              </li>
            ))}
          </ul>
          <label className={styles.check}>
            <input type="checkbox" checked={progress} onChange={(e) => setProgress(e.target.checked)} /> Show which steps are done (worked out from each record&apos;s own fields)
          </label>
          <Button
            size="sm"
            variant="primary"
            loading={busy}
            disabled={!role || picked.length < 2}
            onClick={async () => {
              setBusy(true);
              try {
                const out = await api.stepsPublish(p.connectionId, { model: p.model, view_type: p.viewType, view_id: p.viewId }, role, picked, progress);
                toast.success(`Steps published for ${out.role}`, { description: out.check_note });
                setPicked([]);
                load();
              } catch (err) {
                toast.error(p.errorText(err));
              } finally {
                setBusy(false);
              }
            }}
          >
            Publish steps
          </Button>
          {existing.map((l) => (
            <div key={l.id} className={styles.listItem}>
              <span>Steps for {l.roles.join(", ") || "a role"}{l.active ? "" : " (off)"}</span>
              <Button size="sm" variant="ghost" onClick={async () => {
                try {
                  await api.stepsRemove(p.connectionId, { model: p.model, view_type: p.viewType, view_id: p.viewId }, l.id);
                  toast.success("Steps removed");
                  load();
                } catch (err) {
                  toast.error(p.errorText(err));
                }
              }}>Remove</Button>
            </div>
          ))}
        </section>
      ) : null}
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>What each role sees</h3>
        <div className={styles.row}>{roleSelect(roleA, setRoleA, "First role")}{roleSelect(roleB, setRoleB, "Second role")}</div>
        <Button size="sm" variant="ghost" disabled={!roleA || !roleB} onClick={() => api.compareRoles(p.connectionId, screenOf(p), roleA, roleB).then(setDiff).catch((e) => toast.error(p.errorText(e)))}>
          Compare
        </Button>
        {diff ? (
          <div className={styles.stack} data-testid="vd2c-rolediff">
            <Note tone="info" role="status">{diff.text} <span className={styles.muted}>{diff.based_on}</span></Note>
            {diff.only_a.length ? <p>Only {diff.a}: {diff.only_a.map((d) => d.label).join(", ")}</p> : null}
            {diff.only_b.length ? <p>Only {diff.b}: {diff.only_b.map((d) => d.label).join(", ")}</p> : null}
          </div>
        ) : null}
      </section>
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>Layout comparison test</h3>
        <p className={styles.muted}>
          People in one role get your unpublished changes (layout B); everyone else keeps layout A. Ingenium compares how often a field gets filled in on new records.
        </p>
        {roleSelect(roleB, setRoleB, "Role that gets layout B")}
        <select className={styles.select} aria-label="Field to measure" value={metric} onChange={(e) => setMetric(e.target.value)}>
          <option value="">Field to measure…</option>
          {fieldChoices.map(([n, m]) => <option key={n} value={n}>{m.string || n}</option>)}
        </select>
        <Button
          size="sm"
          variant="primary"
          disabled={!roleB || !metric || !p.ops.length}
          onClick={async () => {
            const body = { ...screenOf(p), ops: p.ops, summary: p.summary, role_b: roleB, metric_field: metric, name: `Test: ${p.fields[metric]?.string ?? metric}` };
            try {
              const out = await api.abStart(p.connectionId, body);
              toast.success("Test started", { description: out.check_note });
              p.onClearOps();
              load();
            } catch (err) {
              askApproval(err, "abtest_start", body, `Start layout test on ${p.model}`);
            }
          }}
        >
          Start test with my changes
        </Button>
        {!p.ops.length ? <p className={styles.muted}>Make the layout B changes on the canvas first.</p> : null}
        <ul className={styles.list}>
          {tests.map((t) => (
            <li key={t.id} className={styles.stack}>
              <div className={styles.listItem}>
                <span>{t.name} <span className={styles.muted}>{t.payload.role_b_name}, {t.payload.status}</span></span>
                <span className={styles.row}>
                  <Button size="sm" variant="ghost" onClick={() => api.abResults(p.connectionId, t.id).then((r) => setResults((x) => ({ ...x, [t.id]: r }))).catch((e) => toast.error(p.errorText(e)))}>Results</Button>
                  {t.payload.status === "running" ? (
                    <Button size="sm" variant="ghost" onClick={() => api.abStop(p.connectionId, t.id).then(() => { toast.success("Test stopped. Everyone has layout A again."); load(); }).catch((e) => askApproval(e, "abtest_stop", { item_id: t.id }, `Stop ${t.name}`))}>Stop</Button>
                  ) : null}
                </span>
              </div>
              {results[t.id] ? (
                <Note tone="info" role="status" data-testid="vd2c-ab-result">
                  {results[t.id].text} <span className={styles.muted}>A: {results[t.id].a.filled}/{results[t.id].a.records}, B: {results[t.id].b.filled}/{results[t.id].b.records}</span>
                </Note>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- Dashboards

function DashboardsTab(p: Props2c) {
  const [opts, setOpts] = useState<DashOptions | null>(null);
  const [spec, setSpec] = useState<DashSpec>({ kind: "graph", chart: "bar", measures: [], rows: [], cols: [], interval: "month" });
  const [preview, setPreview] = useState<DashPreview | null>(null);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.dashOptions(p.connectionId, p.model).then(setOpts).catch((e) => toast.error(p.errorText(e)));
  useEffect(() => { void load(); }, [p.connectionId, p.model]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!opts) return <Note tone="busy" role="status">Reading the options from Odoo…</Note>;
  const max = Math.max(1, ...(preview?.rows ?? []).map((r) => Number(spec.measures[0] ? r[spec.measures[0]] : r.count) || 0));
  return (
    <div className={styles.stack} data-testid="vd2c-dash">
      <p className={styles.muted}>A chart or pivot table of {p.model}, opened from its own menu item. Totals come from Odoo.</p>
      <div className={styles.row}>
        <select className={styles.select} aria-label="Kind" value={spec.kind} onChange={(e) => setSpec({ ...spec, kind: e.target.value as DashSpec["kind"] })}>
          <option value="graph">Chart</option>
          <option value="pivot">Pivot table</option>
        </select>
        {spec.kind === "graph" ? (
          <select className={styles.select} aria-label="Chart type" value={spec.chart} onChange={(e) => setSpec({ ...spec, chart: e.target.value })}>
            <option value="bar">Bars</option>
            <option value="line">Line</option>
            <option value="pie">Pie</option>
          </select>
        ) : null}
      </div>
      <select className={styles.select} aria-label="Group by" value={spec.rows[0] ?? ""} onChange={(e) => setSpec({ ...spec, rows: e.target.value ? [e.target.value] : [] })}>
        <option value="">Group by…</option>
        {opts.groupbys.map((g) => <option key={g.name} value={g.name}>{g.label}</option>)}
      </select>
      {spec.rows[0] && ["date", "datetime"].includes(opts.groupbys.find((g) => g.name === spec.rows[0])?.type ?? "") ? (
        <select className={styles.select} aria-label="Period" value={spec.interval} onChange={(e) => setSpec({ ...spec, interval: e.target.value })}>
          {opts.intervals.map((i) => <option key={i} value={i}>By {i}</option>)}
        </select>
      ) : null}
      <select className={styles.select} aria-label="Number to add up" value={spec.measures[0] ?? ""} onChange={(e) => setSpec({ ...spec, measures: e.target.value ? [e.target.value] : [] })}>
        <option value="">Count of records</option>
        {opts.measures.map((m) => <option key={m.name} value={m.name}>{m.label}</option>)}
      </select>
      <Button size="sm" variant="ghost" disabled={!spec.rows.length} onClick={() => api.dashPreview(p.connectionId, p.model, spec).then(setPreview).catch((e) => toast.error(p.errorText(e)))}>
        Preview with real totals
      </Button>
      {preview ? (
        <div className={styles.stack} data-testid="vd2c-dash-preview">
          <p className={styles.muted}>{preview.note}</p>
          <ul className={styles.list} aria-label="Preview">
            {preview.rows.slice(0, 20).map((r) => {
              const v = Number(spec.measures[0] ? r[spec.measures[0]] : r.count) || 0;
              return (
                <li key={r.label} className={styles.listItem}>
                  <span>{r.label}</span>
                  <span className={styles.row}>
                    <span className={styles.bar} style={{ inlineSize: `${Math.round((v / max) * 120)}px` }} aria-hidden />
                    {v.toLocaleString()}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      <label className={styles.fieldLabel}>
        Name
        <Input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} />
      </label>
      <Button
        size="sm"
        variant="primary"
        loading={busy}
        disabled={!label.trim() || !spec.rows.length}
        onClick={async () => {
          setBusy(true);
          try {
            await api.dashCreate(p.connectionId, { model: p.model, spec, label: label.trim(), make_menu: true });
            toast.success("Dashboard created in Odoo, with a menu item");
            setLabel("");
            void load();
          } catch (err) {
            toast.error(p.errorText(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        Create dashboard
      </Button>
      {opts.dashboards.length ? (
        <>
          <h3 className={styles.sectionTitle}>Dashboards made here</h3>
          <ul className={styles.list}>{opts.dashboards.map((d) => <li key={d.id}>{d.name} <span className={styles.muted}>{d.payload.view_type}</span></li>)}</ul>
          <p className={styles.muted}>Remove them from More… → New screen.</p>
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- Starters

function StartersTab(p: Props2c) {
  const [opts, setOpts] = useState<StarterOption[]>([]);
  const [note, setNote] = useState("");
  const [pick, setPick] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.starters(p.connectionId, p.model).then((o) => { setOpts(o.starters); setNote(o.note); }).catch((e) => toast.error(p.errorText(e)));
  }, [p.connectionId, p.model]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className={styles.stack} data-testid="vd2c-starters">
      <p className={styles.muted}>{note}</p>
      {!opts.length ? <p>There are no industry starters for {p.model} yet.</p> : null}
      <ul className={styles.list} role="radiogroup" aria-label="Industry">
        {opts.map((o) => (
          <li key={o.key}>
            <label className={styles.check}>
              <input type="radio" name="starter" disabled={!o.available} checked={pick === o.key} onChange={() => setPick(o.key)} />
              {o.label} <span className={styles.muted}>({o.fields_found} fields found{o.fields_missing ? `, ${o.fields_missing} not in this database: ${o.missing_labels.slice(0, 4).join(", ")}` : ""})</span>
            </label>
          </li>
        ))}
      </ul>
      <label className={styles.fieldLabel}>
        Name
        <Input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} />
      </label>
      <Button
        size="sm"
        variant="primary"
        loading={busy}
        disabled={!pick || !label.trim()}
        onClick={async () => {
          setBusy(true);
          try {
            const out = await api.starterCreate(p.connectionId, { model: p.model, key: pick, label: label.trim(), make_menu: true });
            toast.success("Starter screen created", { description: out.missing.length ? `Left out (not in this database): ${out.missing.join(", ")}` : undefined });
            p.onOpenScreen("form", out.view_id);
          } catch (err) {
            toast.error(p.errorText(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        Create screen
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------- Publishing

function PublishingTab(p: Props2c) {
  const [policy, setPolicy] = useState<{ required: boolean; note: string | null } | null>(null);
  const [approvals, setApprovals] = useState<Item2c<ApprovalPayload>[]>([]);
  const [scheduled, setScheduled] = useState<Item2c<SchedulePayload>[]>([]);
  const [watches, setWatches] = useState<Item2c<WatchPayload>[]>([]);
  const [digest, setDigest] = useState<DigestOut | null>(null);
  const [note, setNote] = useState("");
  const [when, setWhen] = useState("");
  const [to, setTo] = useState("");
  const load = () => {
    api.approvalPolicy(p.connectionId).then(setPolicy).catch(() => undefined);
    api.approvals(p.connectionId, p.model).then((o) => setApprovals(o.approvals)).catch(() => undefined);
    api.schedules(p.connectionId, p.model).then((o) => setScheduled(o.scheduled)).catch(() => undefined);
    api.watches(p.connectionId, p.model).then((o) => setWatches(o.watches)).catch(() => undefined);
  };
  useEffect(load, [p.connectionId, p.model]);
  const req = { ...screenOf(p), ops: p.ops, summary: p.summary };
  const isoWhen = () => (when ? new Date(when).toISOString() : "");
  const act = (fn: () => Promise<unknown>, ok: string, after?: () => void) =>
    fn().then(() => { toast.success(ok); after?.(); load(); }).catch((e) => toast.error(p.errorText(e)));
  return (
    <div className={styles.stack} data-testid="vd2c-publishing">
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>Approval before publish</h3>
        {policy ? (
          <label className={styles.check}>
            <input type="checkbox" checked={policy.required} onChange={(e) => act(() => api.setApprovalPolicy(p.connectionId, e.target.checked), e.target.checked ? "Changes now need approval" : "Approval is no longer needed")} />
            Changes to screens in this database need someone else&apos;s approval
          </label>
        ) : null}
        {policy?.note ? <Note tone="warning">{policy.note}</Note> : null}
        <Input aria-label="Note for the approver" placeholder="Note for the approver (optional)" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
        <Button size="sm" variant="ghost" disabled={!p.ops.length} onClick={() => act(() => api.approvalRequest(p.connectionId, { ...req, note }), "Sent for approval", () => { setNote(""); p.onClearOps(); })}>
          Ask for approval ({p.ops.length} change{p.ops.length === 1 ? "" : "s"})
        </Button>
        <ul className={styles.list} data-testid="vd2c-approvals">
          {approvals.map((a) => (
            <li key={a.id} className={styles.listItem}>
              <span>
                {a.name} <span className={styles.muted}>by {a.payload.requested_by}{a.payload.identity_verified ? "" : " (not verified)"}, {a.payload.status}{a.payload.failure ? `, ${a.payload.failure}` : ""}</span>
              </span>
              {a.payload.status === "pending" ? (
                <span className={styles.row}>
                  <Button size="sm" variant="primary" onClick={() => act(() => api.approvalDecide(p.connectionId, a.id, true, "", when ? isoWhen() : null), when ? "Approved and scheduled" : "Approved and published", p.onChanged)}>
                    {when ? "Approve for the time below" : "Approve and publish"}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => act(() => api.approvalDecide(p.connectionId, a.id, false), "Rejected")}>Reject</Button>
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>Publish later</h3>
        <label className={styles.fieldLabel}>
          When (your time)
          <Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} data-testid="vd2c-when" />
        </label>
        <Button size="sm" variant="ghost" disabled={!p.ops.length || !when || Boolean(policy?.required)} onClick={() => act(() => api.scheduleCreate(p.connectionId, { ...req, run_at: isoWhen() }), "Scheduled", p.onClearOps)}>
          Schedule my changes
        </Button>
        {policy?.required ? <p className={styles.muted}>With approval on, the approver picks the time.</p> : null}
        <ul className={styles.list}>
          {scheduled.map((s) => (
            <li key={s.id} className={styles.listItem}>
              <span>{s.name} <span className={styles.muted}>{new Date(s.payload.run_at).toLocaleString()}, {s.payload.status}{s.payload.failure ? `, ${s.payload.failure}` : ""}</span></span>
              {s.payload.status === "scheduled" ? <Button size="sm" variant="ghost" onClick={() => act(() => api.scheduleCancel(p.connectionId, s.id), "Cancelled")}>Cancel</Button> : null}
            </li>
          ))}
        </ul>
      </section>
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>After publishing</h3>
        <p className={styles.muted}>Ingenium checks each publish after 5 minutes, 1 hour and 1 day, and keeps a one-click undo.</p>
        <ul className={styles.list} data-testid="vd2c-watches">
          {watches.map((w) => {
            const last = w.payload.results[w.payload.results.length - 1];
            return (
              <li key={w.id} className={styles.listItem}>
                <span>
                  {new Date(w.payload.started_at).toLocaleString()} <span className={styles.muted}>, {w.payload.status}{last ? `, ${last.ok ? "all fine" : last.problems.join("; ")}` : ""}</span>
                </span>
                <span className={styles.row}>
                  <Button size="sm" variant="ghost" onClick={() => act(() => api.watchCheck(p.connectionId, w.id), "Checked")}>Check now</Button>
                  {w.payload.can_undo ? (
                    <Button size="sm" variant="ghost" onClick={() => { if (window.confirm(`Go back to ${w.payload.goes_back_to}?`)) act(() => api.watchUndo(p.connectionId, w.id), "Undone", p.onChanged); }}>Undo</Button>
                  ) : null}
                </span>
              </li>
            );
          })}
        </ul>
      </section>
      <section className={styles.stack}>
        <h3 className={styles.sectionTitle}>Weekly digest</h3>
        <Button size="sm" variant="ghost" onClick={() => api.digestPreview(p.connectionId).then((d) => { setDigest(d); setTo(d.subscription?.to ?? ""); }).catch((e) => toast.error(p.errorText(e)))}>
          Preview this week
        </Button>
        {digest ? <pre className={styles.code} data-testid="vd2c-digest">{digest.text}</pre> : null}
        <div className={styles.row}>
          <Input aria-label="Send to" placeholder="name@company.com" value={to} onChange={(e) => setTo(e.target.value)} />
          <Button size="sm" variant="ghost" onClick={() => api.digestSubscribe(p.connectionId, to, true).then((o) => toast.success("Digest set for Mondays", { description: o.delivery })).catch((e) => toast.error(p.errorText(e)))}>
            Send every Monday
          </Button>
        </div>
      </section>
    </div>
  );
}

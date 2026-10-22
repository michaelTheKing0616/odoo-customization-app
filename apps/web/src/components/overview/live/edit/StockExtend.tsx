"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { api, type MenuNode, type SnapshotModelDetail } from "@/lib/api";
import { parseOptions } from "./gates";
import { PreviewApply, errorText, type Phase } from "./PreviewApply";
import {
  ACCESS_GROUPS, accessSpec, automationSpec, overlayBody,
  type AccessInput, type AutomationInput, type ExtendViewInput,
} from "./stock-specs";
import { Term } from "@/components/ui/Term";

type Detail = SnapshotModelDetail;
type Props = { connectionId: string; d: Detail; onDone: () => void; onCancel: () => void };

const input =
  "w-full rounded-md border border-border-subtle bg-surface-raised px-2.5 py-1.5 text-ui-body text-ink focus:outline-none focus:ring-2 focus:ring-accent";
const box = "space-y-3 rounded-md border border-border-subtle bg-surface-muted p-3";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block space-y-1 text-ui-meta text-muted"><span>{label}</span>{children}</label>;
}

function Actions({ onNext, onCancel, next, disabled, testId }: {
  onNext: () => void; onCancel: () => void; next: string; disabled?: boolean; testId: string;
}) {
  return (
    <div className="flex gap-2">
      <Button variant="secondary" size="sm" onClick={onNext} disabled={disabled} data-testid={testId}>{next}</Button>
      <Button variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
    </div>
  );
}

function ErrorLine({ message, suffix = "" }: { message: string; suffix?: string }) {
  return <p role="alert" className="text-ui-meta text-status-critical-strong" data-testid="apply-error">{`That didn't work: ${message}${suffix}`}</p>;
}

const nameOf = (d: Detail, f: string) => d.fields.find((x) => x.name === f)?.string || f;

/** Same Apply App Studio uses; access rules in the plan are always applied, so only automations need a flag. */
async function applySpec(connectionId: string, spec: Record<string, unknown>, flags: { automations?: boolean }) {
  await api.applyModuleSpec(connectionId, {
    spec, apply_views: false, apply_menus: false, apply_smart_buttons: false,
    apply_automations: !!flags.automations,
  });
}

/** Add or move a field on Odoo's own form or list through an extension view. The original screen is not edited. */
export function ViewExtender({ connectionId, d, onDone, onCancel }: Props) {
  const onForm = new Set(d.views.form_fields);
  const [v, setV] = useState<ExtendViewInput>({ model: d.model, viewType: "form", op: "add", field: "", after: d.views.form_fields.at(-1) ?? "" });
  const [phase, setPhase] = useState<Phase>({ kind: "edit" });
  const [arch, setArch] = useState("");
  const candidates = v.op === "move" ? d.views.form_fields : d.fields.filter((f) => v.viewType === "list" || !onForm.has(f.name)).map((f) => f.name);
  const body = overlayBody(v);
  async function preview() {
    try {
      const out = await api.overlayPreview(connectionId, body);
      if (out.issues.length) { setPhase({ kind: "error", message: out.issues.join(" ") }); return; }
      setArch(out.xpath_arch);
      setPhase({ kind: "preview" });
    } catch (err) { setPhase({ kind: "error", message: errorText(err) }); }
  }
  async function apply() {
    setPhase({ kind: "applying" });
    try { await api.applyOverlayOp(connectionId, body); onDone(); } catch (err) { setPhase({ kind: "error", message: errorText(err) }); }
  }
  if (phase.kind !== "edit" && arch) {
    const where = v.after ? `after “${nameOf(d, v.after)}”` : "at the end";
    return (
      <div className="space-y-2" data-testid="extend-view-preview">
        <PreviewApply
          title={`Extend the ${v.viewType} screen of ${d.label || d.model}`}
          changes={[`${v.op === "move" ? "Move" : "Show"} “${nameOf(d, v.field)}” ${where}`,
            "Saved as an extension view; Odoo's original screen stays as it is"]}
          phase={phase} onBack={() => { setArch(""); setPhase({ kind: "edit" }); }} onApply={() => void apply()} />
        <pre className="max-h-40 overflow-auto rounded-md bg-surface-raised p-2 text-ui-mono text-muted">{arch}</pre>
      </div>
    );
  }
  return (
    <div className={box} data-testid="extend-view">
      <p className="text-ui-body font-medium text-ink">Extend this view</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <Row label="Screen">
          <select className={input} value={v.viewType} aria-label="Screen"
            onChange={(e) => {
              const vt = e.target.value as "form" | "list";
              setV({ ...v, viewType: vt, op: vt === "list" ? "add" : v.op, after: vt === "list" ? "" : v.after });
            }}>
            <option value="form">Form</option><option value="list">List</option>
          </select>
        </Row>
        <Row label="Change">
          <select className={input} value={v.op} aria-label="Change" disabled={v.viewType === "list"}
            onChange={(e) => setV({ ...v, op: e.target.value as "add" | "move", field: "" })}>
            <option value="add">Add a field</option><option value="move">Move a field</option>
          </select>
        </Row>
        <Row label="Field">
          <select className={input} value={v.field} aria-label="Field" onChange={(e) => setV({ ...v, field: e.target.value })}>
            <option value="">Choose a field</option>
            {candidates.map((f) => <option key={f} value={f}>{nameOf(d, f)}</option>)}
          </select>
        </Row>
        <Row label="Place it">
          <select className={input} value={v.after} aria-label="Place it" onChange={(e) => setV({ ...v, after: e.target.value })}>
            {v.viewType === "list" || v.op === "add" ? <option value="">At the end</option> : null}
            {v.viewType === "form" ? d.views.form_fields.filter((f) => f !== v.field).map((f) => <option key={f} value={f}>After {nameOf(d, f)}</option>) : null}
          </select>
        </Row>
      </div>
      {phase.kind === "error" ? <ErrorLine message={phase.message} /> : null}
      <Actions next="Preview change" testId="extend-view-preview-btn" onNext={() => void preview()} onCancel={onCancel}
        disabled={!v.field || (v.op === "move" && !v.after)} />
    </div>
  );
}

/** Automation rule or dated reminder on Odoo's own model, through App Studio's apply checks. */
export function AutomationAdder({ connectionId, d, onDone, onCancel }: Props) {
  const dates = d.fields.filter((f) => f.type === "date" || f.type === "datetime");
  const users = d.fields.filter((f) => f.type === "many2one" && f.relation === "res.users");
  const [a, setA] = useState<AutomationInput>({
    model: d.model, name: "", when: "created", dateField: dates[0]?.name, days: 1, direction: "before",
    action: users.length ? "todo" : "set", userField: users[0]?.name, summary: "",
  });
  const [phase, setPhase] = useState<Phase>({ kind: "edit" });
  const ready = !!a.name && (a.when !== "date" || !!a.dateField) && (a.action === "todo" ? !!a.userField : !!a.setField);
  async function apply() {
    setPhase({ kind: "applying" });
    try { await applySpec(connectionId, automationSpec(a), { automations: true }); onDone(); } catch (err) { setPhase({ kind: "error", message: errorText(err) }); }
  }
  if (phase.kind !== "edit") {
    const when = a.when === "created" ? "When a record is created" : a.when === "updated" ? "When a record is changed"
      : `${a.days} day${a.days === 1 ? "" : "s"} ${a.direction} ${nameOf(d, a.dateField ?? "")} (checked by a scheduled action)`;
    const what = a.action === "todo" ? `Schedule a to-do “${a.summary || a.name}” for ${nameOf(d, a.userField ?? "")}`
      : `Set ${nameOf(d, a.setField ?? "")} to “${a.setValue ?? ""}”`;
    return <PreviewApply title={`Add the automation rule “${a.name}”`} changes={[when, what]} phase={phase}
      onBack={() => setPhase({ kind: "edit" })} onApply={() => void apply()} />;
  }
  return (
    <div className={box} data-testid="add-automation-form">
      <p className="text-ui-body font-medium text-ink">Add an <Term tech="base.automation">automation rule</Term></p>
      <div className="grid gap-2 sm:grid-cols-2">
        <Row label="Name"><input className={input} aria-label="Name" value={a.name} onChange={(e) => setA({ ...a, name: e.target.value })} /></Row>
        <Row label="When">
          <select className={input} aria-label="When" value={a.when} onChange={(e) => setA({ ...a, when: e.target.value as AutomationInput["when"] })}>
            <option value="created">A record is created</option><option value="updated">A record is changed</option>
            {dates.length ? <option value="date">Days before or after a date</option> : null}
          </select>
        </Row>
        {a.when === "date" ? (
          <>
            <Row label="Date"><select className={input} aria-label="Date" value={a.dateField} onChange={(e) => setA({ ...a, dateField: e.target.value })}>
              {dates.map((f) => <option key={f.name} value={f.name}>{f.string || f.name}</option>)}</select></Row>
            <Row label="Days"><div className="flex gap-2">
              <input className={input} type="number" min={0} aria-label="Days" value={a.days} onChange={(e) => setA({ ...a, days: Number(e.target.value) })} />
              <select className={input} aria-label="Before or after" value={a.direction} onChange={(e) => setA({ ...a, direction: e.target.value as "before" | "after" })}>
                <option value="before">before</option><option value="after">after</option></select></div></Row>
          </>
        ) : null}
        <Row label="Do">
          <select className={input} aria-label="Do" value={a.action} onChange={(e) => setA({ ...a, action: e.target.value as "todo" | "set" })}>
            {users.length ? <option value="todo">Schedule a to-do</option> : null}<option value="set">Set a field</option>
          </select>
        </Row>
        {a.action === "todo" ? (
          <>
            <Row label="To-do"><input className={input} aria-label="To-do" value={a.summary} placeholder={a.name} onChange={(e) => setA({ ...a, summary: e.target.value })} /></Row>
            <Row label="Assign to"><select className={input} aria-label="Assign to" value={a.userField} onChange={(e) => setA({ ...a, userField: e.target.value })}>
              {users.map((f) => <option key={f.name} value={f.name}>{f.string || f.name}</option>)}</select></Row>
          </>
        ) : (
          <>
            <Row label="Field"><select className={input} aria-label="Field to set" value={a.setField ?? ""} onChange={(e) => setA({ ...a, setField: e.target.value })}>
              <option value="">Choose a field</option>
              {d.fields.filter((f) => ["char", "text", "boolean", "integer", "float", "selection"].includes(f.type)).map((f) => <option key={f.name} value={f.name}>{f.string || f.name}</option>)}</select></Row>
            <Row label="Value"><input className={input} aria-label="Value" value={a.setValue ?? ""} onChange={(e) => setA({ ...a, setValue: e.target.value })} /></Row>
          </>
        )}
      </div>
      {!users.length ? <p className="text-ui-meta text-muted">To-dos need a user field on this record to know who gets them.</p> : null}
      <Actions next="Review change" testId="automation-review" onNext={() => setPhase({ kind: "preview" })} onCancel={onCancel} disabled={!ready} />
    </div>
  );
}

/** Access rights (and an own-records limit) on Odoo's own model. */
export function AccessAdder({ connectionId, d, onDone, onCancel }: Props) {
  const [a, setA] = useState<AccessInput>({ model: d.model, group: "base.group_user", read: true, write: false, create: false, remove: false, ownOnly: false });
  const [phase, setPhase] = useState<Phase>({ kind: "edit" });
  const group = ACCESS_GROUPS.find((g) => g.value === a.group)?.label ?? a.group;
  const can = [a.read && "read", a.write && "edit", a.create && "create", a.remove && "delete"].filter(Boolean).join(", ");
  async function apply() {
    setPhase({ kind: "applying" });
    try { await applySpec(connectionId, accessSpec(a), {}); onDone(); } catch (err) { setPhase({ kind: "error", message: errorText(err) }); }
  }
  if (phase.kind !== "edit") {
    return <PreviewApply title={`Add access rights to ${d.label || d.model}`} phase={phase}
      changes={[`${group} can ${can}`, a.ownOnly ? "Only for records they created; if this group had open access here, that is switched off so the limit takes effect" : "For all records"]}
      onBack={() => setPhase({ kind: "edit" })} onApply={() => void apply()} />;
  }
  const check = (k: "read" | "write" | "create" | "remove" | "ownOnly", label: string) => (
    <label className="flex items-center gap-2 text-ui-body text-ink"><input type="checkbox" checked={a[k]} onChange={(e) => setA({ ...a, [k]: e.target.checked })} />{label}</label>
  );
  return (
    <div className={box} data-testid="add-access-form">
      <p className="text-ui-body font-medium text-ink">Add <Term tech="ir.model.access">access rights</Term></p>
      <Row label="Who"><select className={input} aria-label="Who" value={a.group} onChange={(e) => setA({ ...a, group: e.target.value })}>
        {ACCESS_GROUPS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}</select></Row>
      <div className="flex flex-wrap gap-4">{check("read", "Read")}{check("write", "Edit")}{check("create", "Create")}{check("remove", "Delete")}</div>
      {check("ownOnly", "Only records they created")}
      <Actions next="Review change" testId="access-review" onNext={() => setPhase({ kind: "preview" })} onCancel={onCancel} disabled={!can} />
    </div>
  );
}

/** A menu (and the window action it opens) for Odoo's own model, under an app the user picks. */
export function MenuAdder({ connectionId, d, onDone, onCancel }: Props) {
  const [apps, setApps] = useState<MenuNode[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [parent, setParent] = useState<number | null>(null);
  const [name, setName] = useState(d.label || d.model);
  const [phase, setPhase] = useState<Phase>({ kind: "edit" });
  useEffect(() => {
    let live = true;
    api.listMenuTree(connectionId, { rootsOnly: true })
      .then((rows) => { if (live) { setApps(rows); setParent(rows[0]?.id ?? null); } })
      .catch((err) => { if (live) { setApps([]); setLoadError(errorText(err)); } });
    return () => { live = false; };
  }, [connectionId]);
  async function apply() {
    if (parent == null) return;
    setPhase({ kind: "applying" });
    try {
      const action = await api.createWindowAction(connectionId, { name, model: d.model, view_mode: "list,form" });
      await api.createBuilderMenu(connectionId, { name, parent_id: parent, action_id: action.id });
      onDone();
    } catch (err) { setPhase({ kind: "error", message: errorText(err) }); }
  }
  const app = apps?.find((m) => m.id === parent)?.name ?? "";
  if (phase.kind !== "edit") {
    return <PreviewApply title={`Add a menu for ${d.label || d.model}`} phase={phase}
      changes={[`Add “${name}” under ${app}`, `It opens ${d.label || d.model} as a list, with a form for each record`]}
      onBack={() => setPhase({ kind: "edit" })} onApply={() => void apply()} />;
  }
  return (
    <div className={box} data-testid="add-menu-form">
      <p className="text-ui-body font-medium text-ink">Add a menu</p>
      {apps === null ? <p className="text-ui-meta text-muted">Loading your apps…</p> : apps.length === 0 ? (
        <p className="text-ui-meta text-muted">{loadError ? `We couldn't read your menus: ${loadError}` : "No apps to put the menu under yet."}</p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          <Row label="Under app"><select className={input} aria-label="Under app" value={parent ?? ""} onChange={(e) => setParent(Number(e.target.value))}>
            {apps.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Row>
          <Row label="Menu name"><input className={input} aria-label="Menu name" value={name} onChange={(e) => setName(e.target.value)} /></Row>
        </div>
      )}
      <Actions next="Review change" testId="menu-review" onNext={() => setPhase({ kind: "preview" })} onCancel={onCancel} disabled={!apps?.length || !name || parent == null} />
    </div>
  );
}

type CodeKind = "selection_options" | "computed_field" | "behaviour";
type CodeStep = { kind: "edit" } | { kind: "drafted" } | { kind: "testing" } | { kind: "tested"; validationId: string | null }
  | { kind: "publishing" } | { kind: "published"; message: string } | { kind: "error"; message: string };

/** Custom code for a built-in model (Odoo.sh / self-hosted): draft an extension module, test it on a test copy, then publish. */
export function CodeExtender({ connectionId, d, onDone, onCancel }: Props) {
  const choices = d.fields.filter((f) => f.type === "selection" && !f.custom);
  const [kind, setKind] = useState<CodeKind>(choices.length ? "selection_options" : "computed_field");
  const [field, setField] = useState(choices[0]?.name ?? "");
  const [label, setLabel] = useState("");
  const [options, setOptions] = useState("");
  const [draft, setDraft] = useState<{ code: string; depends: string[]; technical_name: string } | null>(null);
  const [zip, setZip] = useState("");
  const [step, setStep] = useState<CodeStep>({ kind: "edit" });
  const fail = (err: unknown) => setStep({ kind: "error", message: errorText(err) });
  async function makeDraft() {
    try {
      const out = await api.getExtensionScaffold(connectionId, {
        model: d.model, kind, field_name: kind === "behaviour" ? null : field, label: label || null,
        options: kind === "selection_options" ? parseOptions(options) : null,
      });
      setDraft(out); setStep({ kind: "drafted" });
    } catch (err) { fail(err); }
  }
  async function test() {
    if (!draft) return;
    setStep({ kind: "testing" });
    try {
      const pkg = await api.exportCodeStudioOptionA(connectionId, {
        name: `${d.label || d.model} extension`, model: d.model, code: draft.code,
        technical_name: draft.technical_name, depends: draft.depends, as_extension: true,
      });
      setZip(pkg.content_base64);
      const run = await api.runSandbox(connectionId, { technical_name: pkg.technical_name, zip_base64: pkg.content_base64 });
      if (!run.ok) { setStep({ kind: "error", message: run.message || "The test copy didn't install the extension." }); return; }
      setStep({ kind: "tested", validationId: run.validation_id ?? null });
    } catch (err) { fail(err); }
  }
  async function publish(validationId: string | null) {
    setStep({ kind: "publishing" });
    try {
      const out = await api.promoteModule(connectionId, { technical_name: draft?.technical_name, zip_base64: zip, validation_id: validationId });
      setStep({ kind: "published", message: out.message });
      onDone();
    } catch (err) { fail(err); }
  }
  const editing = step.kind === "edit" || (step.kind === "error" && !draft);
  return (
    <div className={box} data-testid="extend-code">
      <p className="text-ui-body font-medium text-ink">Extend {d.label || d.model} with custom code</p>
      <p className="text-ui-meta text-muted">For what a screen change can&apos;t do. We draft a small extension module, test it on a test copy, then you publish it.</p>
      {editing ? (
        <>
          <Row label="What should it do">
            <select className={input} aria-label="What should it do" value={kind} onChange={(e) => setKind(e.target.value as CodeKind)}>
              {choices.length ? <option value="selection_options">Add options to one of Odoo&apos;s choice fields</option> : null}
              <option value="computed_field">Add a calculated field</option>
              <option value="behaviour">Change what happens on save</option>
            </select>
          </Row>
          {kind === "selection_options" ? (
            <>
              <Row label="Choice field"><select className={input} aria-label="Choice field" value={field} onChange={(e) => setField(e.target.value)}>
                {choices.map((f) => <option key={f.name} value={f.name}>{f.string || f.name}</option>)}</select></Row>
              <Row label="New options, one per line (value: Label)"><textarea className={input} rows={3} aria-label="New options" value={options} onChange={(e) => setOptions(e.target.value)} /></Row>
            </>
          ) : kind === "computed_field" ? (
            <Row label="Field label"><input className={input} aria-label="Field label" value={label} onChange={(e) => { setLabel(e.target.value); setField(e.target.value); }} /></Row>
          ) : null}
          {step.kind === "error" ? <ErrorLine message={step.message} /> : null}
          <Actions next="Draft the code" testId="code-draft" onNext={() => void makeDraft()} onCancel={onCancel}
            disabled={kind === "selection_options" ? !field || !options.trim() : kind === "computed_field" ? !label : false} />
        </>
      ) : (
        <>
          <pre className="max-h-56 overflow-auto rounded-md bg-surface-raised p-2 text-ui-mono text-ink" data-testid="code-draft-text">{draft?.code}</pre>
          {step.kind === "error" ? <ErrorLine message={step.message} suffix=" Nothing was published." /> : null}
          {step.kind === "tested" ? <p className="text-ui-meta text-ink" data-testid="code-tested">It installed cleanly on a test copy.</p> : null}
          {step.kind === "published" ? <p className="text-ui-meta text-ink" data-testid="code-published">{step.message || "Published to Odoo."}</p> : (
            <div className="flex gap-2">
              {step.kind === "tested" || step.kind === "publishing" ? (
                <Button variant="primary" size="sm" disabled={step.kind === "publishing"} data-testid="code-publish"
                  onClick={() => { if (step.kind === "tested") void publish(step.validationId); }}>
                  {step.kind === "publishing" ? "Publishing…" : "Publish to Odoo"}
                </Button>
              ) : (
                <Button variant="primary" size="sm" disabled={step.kind === "testing"} data-testid="code-test" onClick={() => void test()}>
                  {step.kind === "testing" ? "Testing on a test copy…" : "Test on a test copy"}
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={onCancel} disabled={step.kind === "testing" || step.kind === "publishing"}>Cancel</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

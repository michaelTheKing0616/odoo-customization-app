"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type { EngineOp, EngineViewType } from "@/lib/api/view-engine";
import { DEVICES, nextSelection } from "@/lib/viewDesigner2a";
import { describeOp, indexTree, nodeName } from "@/lib/viewEngineOps";
import { BuilderSheet, type BuilderTab } from "./BuilderSheet";
import { Builder2cSheet, type Tab2c } from "./Builder2cSheet";
import { FieldDepsPanel, TourCard, VisionFilters } from "./Insights2c";
import { useDesigner2c } from "./useDesigner2c";
import { BuildPanel } from "./BuildPanel";
import { ChecksPanel } from "./ChecksPanel";
import { CommandBar } from "./CommandBar";
import { FieldExtras, SaveSection, ScreenSettings } from "./ItemExtras";
import { useDesigner2b } from "./useDesigner2b";
import { CommentsPanel } from "./CommentsPanel";
import { EngineCanvas } from "./EngineCanvas";
import { HistoryPanel } from "./HistoryPanel";
import { RecordAccessSheet } from "./RecordAccessSheet";
import { RulesPanel } from "./RulesPanel";
import { useDesigner2a } from "./useDesigner2a";
import { VersionsSplit } from "./VersionsSplit";
import { WhoCanSeePanel } from "./WhoCanSeePanel";
import { FieldsPanel } from "./FieldsPanel";
import { Inspector } from "./Inspector";
import { LayersTree } from "./LayersTree";
import { useViewDesigner, type Device } from "./useViewDesigner";
import { Note } from "../view-designer/Note";
import { WriteModeNote } from "../view-designer/WriteModeNote";
import { PublishMoment } from "./PublishMoment";
import { SelectionCount } from "@/components/ui/craft";
import { CanvasSkeleton } from "./Skeleton";
import styles from "./ViewDesigner.module.css";
import { Term } from "@/components/ui/Term";

const DEVICE_WIDTH = Object.fromEntries(DEVICES.map((d) => [d.id, d.width])) as Record<Device, number>;

/** View Designer: top bar, layers and fields, live canvas, properties, history and comments. */
export function ViewDesignerShell({ connectionId }: { connectionId: string }) {
  const s = useViewDesigner(connectionId);
  const x = useDesigner2a(s, connectionId);
  const y = useDesigner2b(s, connectionId);
  const z = useDesigner2c(s, connectionId);
  const [sheet2cOpen, setSheet2cOpen] = useState(false);
  const [sheet2cTab, setSheet2cTab] = useState<Tab2c>("insights");
  const open2c = (t: Tab2c) => {
    setSheet2cTab(t);
    setSheet2cOpen(true);
  };
  const [leftTab, setLeftTab] = useState<"layers" | "fields" | "add">("layers");
  const [rightTab, setRightTab] = useState<"properties" | "checks" | "history" | "comments">("properties");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetTab, setSheetTab] = useState<BuilderTab>("screen");
  const [hideRuleFor, setHideRuleFor] = useState<string | null>(null);
  const openSheet = (t: BuilderTab) => {
    setSheetTab(t);
    setSheetOpen(true);
  };
  const [modelDraft, setModelDraft] = useState(s.model);
  const [announce, setAnnounce] = useState("");

  const selected = s.selectedId && s.index ? s.index.byId.get(s.selectedId) ?? null : null;
  const selectedNodes = s.index ? s.selectedIds.map((id) => s.index!.byId.get(id)).filter((n): n is NonNullable<typeof n> => Boolean(n)) : [];
  const select = (id: string, additive = false) => s.setSelectedIds(nextSelection(s.selectedIds, id, additive));
  const jump = (id: string) => {
    select(id);
    setRightTab("properties");
    document.querySelector(`[data-node-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "center" });
  };
  const addOps = (next: EngineOp[], summary: string) => {
    setAnnounce(summary);
    s.addOps(next, summary);
  };

  const addOp = (op: EngineOp) => {
    if (s.index) setAnnounce(describeOp(op, s.index, s.fieldLabel));
    s.addOp(op);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const t = e.target as HTMLElement | null;
      const typing = Boolean(t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable));
      if (mod && e.key.toLowerCase() === "k") {
        // The designer's own command bar takes ⌘K here.
        e.preventDefault();
        e.stopImmediatePropagation();
        x.setCommandOpen(true);
        return;
      }
      if (!mod && !typing && e.key.toLowerCase() === "c") {
        x.setCommentsOn(!x.commentsOn);
        if (!x.commentsOn) setRightTab("comments");
        return;
      }
      if (!mod || e.key.toLowerCase() !== "z" || typing) return;
      e.preventDefault();
      if (e.shiftKey) s.redoLast();
      else s.undo();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [s, x]);

  const extras = {
    connectionId,
    model: s.model,
    viewType: s.viewType,
    viewId: s.viewId,
    fields: s.base?.fields ?? {},
    onOp: addOp,
    onOps: addOps,
    errorText: x.errorText,
  };
  const recs = s.records?.records ?? [];
  const recIdx = recs.findIndex((r) => r.id === s.recordId);
  const pending = s.compiled?.steps.length ?? 0;

  return (
    <div className={styles.shell} data-testid="view-designer">
      <PublishMoment connectionId={connectionId} count={s.publishCount} />
      <SelectionCount count={s.selectedIds.length} noun="items" />
      <header className={styles.topBar}>
        <form
          className={styles.screenPicker}
          onSubmit={(e) => {
            e.preventDefault();
            s.setSelectedId(null);
            s.setModel(modelDraft.trim());
          }}
        >
          <label className={styles.srOnly} htmlFor="vd-model"><Term tech="ir.model">Record type</Term></label>
          <Input id="vd-model" value={modelDraft} onChange={(e) => setModelDraft(e.target.value)} placeholder="res.partner…" spellCheck={false} />
          <label className={styles.srOnly} htmlFor="vd-type">Screen</label>
          <select
            id="vd-type"
            value={s.viewType}
            onChange={(e) => {
              s.setSelectedId(null);
              s.setViewId(null);
              s.setViewType(e.target.value as EngineViewType);
            }}
          >
            <option value="form">Form</option>
            <option value="list">List</option>
            <option value="kanban">Cards</option>
            <option value="search">Search</option>
            <option value="calendar">Calendar</option>
          </select>
          <Button size="sm" type="submit">Open</Button>
        </form>

        <div className={styles.stepper} aria-label="Sample records">
          <Button size="sm" variant="ghost" aria-label="Previous record" disabled={recIdx <= 0} onClick={() => s.setRecordId(recs[recIdx - 1]?.id ?? null)}>
            ‹
          </Button>
          <span data-testid="vd-record-pos">
            {recs.length ? `Record ${recIdx + 1} of ${recs.length}` : "No records yet"}
          </span>
          <Button size="sm" variant="ghost" aria-label="Next record" disabled={recIdx < 0 || recIdx >= recs.length - 1} onClick={() => s.setRecordId(recs[recIdx + 1]?.id ?? null)}>
            ›
          </Button>
          <Button size="sm" variant="ghost" disabled={!s.records?.picks.longest} onClick={() => s.setRecordId(s.records?.picks.longest ?? null)}>
            Longest
          </Button>
          <Button size="sm" variant="ghost" disabled={!s.records?.picks.emptiest} onClick={() => s.setRecordId(s.records?.picks.emptiest ?? null)}>
            Emptiest
          </Button>
        </div>

        <div className={styles.previewAs} role="group" aria-label="Preview as">
          <span className={styles.muted}>Preview as</span>
          <select
            className={styles.select}
            aria-label="Role"
            value={x.previewRole}
            onChange={(e) => x.setPreviewRole(e.target.value)}
            data-testid="vd-preview-role"
          >
            <option value="">You (all items)</option>
            {x.roles.map((r) => (
              <option key={r.xmlid} value={r.xmlid}>{r.name}</option>
            ))}
          </select>
          {DEVICES.map((d) => (
            <Button key={d.id} size="sm" variant="ghost" aria-pressed={s.device === d.id} onClick={() => s.setDevice(d.id)}>
              {d.label}
            </Button>
          ))}
          <Button size="sm" variant="ghost" aria-pressed={x.versionsOpen} onClick={() => x.setVersionsOpen(!x.versionsOpen)} data-testid="vd-versions-toggle">
            <span data-testid="vd-version">{s.base ? `Odoo ${s.base.major}` : "Versions"}</span>, compare
          </Button>
          <Button size="sm" variant="ghost" aria-pressed={x.commentsOn} onClick={() => { x.setCommentsOn(!x.commentsOn); setRightTab("comments"); }}>
            Comments
          </Button>
          <Button size="sm" variant="ghost" onClick={() => x.setCommandOpen(true)} aria-keyshortcuts="Meta+K">⌘K</Button>
        </div>

        <div className={styles.actions}>
          <Button size="sm" variant="ghost" onClick={() => open2c("insights")} data-testid="vd-insights">Insights</Button>
          <Button size="sm" variant="ghost" onClick={() => open2c("publishing")} data-testid="vd-publishing">Publishing</Button>
          <Button size="sm" variant="ghost" onClick={() => openSheet("screen")} data-testid="vd-more">More…</Button>
          <Button size="sm" variant="ghost" disabled={!s.ops.length} onClick={s.undo}>Undo</Button>
          <Button
            variant="primary"
            size="sm"
            loading={s.publishing}
            disabled={!pending || s.offline || s.compiling || Boolean(s.compiled?.blocking)}
            onClick={() => void s.publish()}
            data-testid="vd-publish"
          >
            {s.publishing ? "Publishing…" : pending ? `Publish changes (${pending})` : "Publish changes"}
          </Button>
        </div>
      </header>

      <aside className={styles.left} aria-label="Layers and fields">
        <div role="tablist" className={styles.panelTabs}>
          <button type="button" role="tab" aria-selected={leftTab === "layers"} onClick={() => setLeftTab("layers")}>Layers</button>
          <button type="button" role="tab" aria-selected={leftTab === "fields"} onClick={() => setLeftTab("fields")}>Fields</button>
          <button type="button" role="tab" aria-selected={leftTab === "add"} onClick={() => setLeftTab("add")}>Add</button>
        </div>
        {s.tree && s.index ? (
          leftTab === "add" ? (
            <BuildPanel
              connectionId={connectionId}
              model={s.model}
              viewType={s.viewType}
              viewId={s.viewId}
              ops={s.ops}
              tree={s.tree}
              selected={selected}
              onOps={addOps}
              onFieldsChanged={() => void s.reload()}
              errorText={x.errorText}
            />
          ) : leftTab === "layers" ? (
            <LayersTree
              tree={s.tree}
              index={s.index}
              selectedId={s.selectedId}
              onSelect={(id: string) => select(id)}
              onOp={addOp}
              onRefused={(m) => {
                setAnnounce(m);
                toast(m);
              }}
            />
          ) : (
            <FieldsPanel
              connectionId={connectionId}
              model={s.model}
              index={s.index}
              fields={s.base?.fields ?? {}}
              selectedLabel={selected?.anchor ? nodeName(selected) : null}
              onAdd={(field) => {
                if (!selected) return;
                const inside = ["group", "page"].includes(selected.tag);
                addOp({ op: "insert_field", field, target: selected.id, position: inside ? "inside" : "after" });
              }}
            />
          )
        ) : null}
      </aside>

      <main className={styles.canvas} aria-label="Screen preview" onClick={() => s.setSelectedId(null)}>
        {s.loading ? <CanvasSkeleton /> : null}
        {s.offline ? (
          <Note tone="warning" as="div" role="status" data-testid="vd-offline">
            <p>You&apos;re offline. This is the last version of the screen Ingenium loaded, read-only until you reconnect.</p>
            <Button size="sm" onClick={() => void s.reload()}>Retry</Button>
          </Note>
        ) : null}
        <WriteModeNote connectionId={connectionId} />
        {s.loadError ? (
          <Note tone="danger" as="div" role="alert">
            <p>Can&apos;t open this screen. {s.loadError}</p>
            <Button size="sm" onClick={() => void s.reload()}>Try again</Button>
          </Note>
        ) : null}
        {x.versionsOpen && s.base ? (
          <VersionsSplit
            connectionId={connectionId}
            model={s.model}
            viewType={s.viewType}
            ops={s.ops}
            width={DEVICE_WIDTH[s.device]}
            onClose={() => x.setVersionsOpen(false)}
            errorText={x.errorText}
          />
        ) : null}
        {y.others.length ? (
          <div className={styles.banner} role="status" data-testid="vd-presence">
            <span>{y.others.join(", ")} {y.others.length === 1 ? "is" : "are"} also editing this screen. Whoever publishes second will be asked to reload first.</span>
          </div>
        ) : null}
        {y.guard && y.guard.has_layer && !y.guard.ok ? (
          <div className={styles.banner} role="alert" data-testid="vd-guard-banner">
            <span>{y.guard.summary}</span>
            <Button size="sm" variant="ghost" onClick={() => openSheet("guard")}>Review</Button>
          </div>
        ) : null}
        {x.preview ? (
          <div className={styles.banner} role="status" data-testid="vd-preview-summary">
            <span>
              {x.preview.summary} <span className={styles.muted}>{x.preview.based_on}</span>
            </span>
            <Button size="sm" variant="ghost" onClick={() => x.setPreviewRole("")}>Stop preview</Button>
          </div>
        ) : null}
        {x.scrub ? (
          <div className={styles.banner} role="status" data-testid="vd-scrub-banner">
            <span>Showing an earlier version: {x.scrub.label}. Nothing is changed.</span>
            <Button size="sm" variant="ghost" onClick={() => x.setScrub(null)}>Back to now</Button>
          </div>
        ) : null}
        {s.tree && s.index && !s.loading && !x.versionsOpen ? (
          <div className={styles.device} style={{ maxWidth: DEVICE_WIDTH[s.device] }} data-device={s.device} data-simulate={z.simulate || undefined}>
            {z.sample ? (
              <p className={styles.row} role="status" data-testid="vd2c-sample-banner">
                <span className={styles.sampleBadge}>Sample</span>
                <span className={styles.muted}>Made-up values for the preview. Nothing here comes from your database.</span>
                <Button size="sm" variant="ghost" onClick={() => z.setSample(null)}>Back to real records</Button>
              </p>
            ) : recs.length === 0 ? <p className={styles.muted}>No records yet, so fields show as empty. Insights → Sample data fills the preview with labelled samples.</p> : null}
            {x.scrub ? (
              <EngineCanvas
                tree={x.scrub.tree}
                index={indexTree(x.scrub.tree)}
                record={s.record}
                selectedId={null}
                onSelect={() => undefined}
                onMove={() => undefined}
                onInsertField={() => undefined}
                readOnly
              />
            ) : (
              <EngineCanvas
                tree={s.tree}
                index={s.index}
                record={z.sample ?? s.record}
                selectedId={s.selectedId}
                onSelect={select}
                onMove={(node, target, position) => addOp({ op: "move", node, target, position })}
                onInsertField={(field, target, position) => addOp({ op: "insert_field", field, target, position })}
                multiSelected={s.selectedIds}
                markers={x.markers ?? undefined}
                preview={x.preview?.visibility ?? null}
                commentCounts={x.commentsOn ? x.commentCounts : null}
                heat={z.heat}
                cursors={z.cursors}
                tourFocus={z.tourFocus}
                onOpenComments={(id) => {
                  select(id);
                  setRightTab("comments");
                }}
              />
            )}
          </div>
        ) : null}
        {z.tour ? <TourCard steps={z.tour} at={z.tourAt} onAt={z.setTourAt} onEnd={z.endTour} /> : null}
        <VisionFilters />
        {s.compiled?.warnings.length ? (
          <ul className={styles.notice} role="note">
            {s.compiled.warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        ) : null}
        {selected ? (
          <p className={styles.hintStrip} data-testid="vd-key-hints">
            Alt + ↑ ↓ to reorder, Alt + ← to move out, Alt + → to move into the group above. ⇧ or ⌘ click to pick several. C for comments. ⌘ K for commands. ⌘ Z to undo.
          </p>
        ) : null}
      </main>

      <aside className={styles.right} aria-label="Properties">
        <div role="tablist" className={styles.panelTabs}>
          <button type="button" role="tab" aria-selected={rightTab === "properties"} onClick={() => setRightTab("properties")}>Properties</button>
          <button type="button" role="tab" aria-selected={rightTab === "checks"} onClick={() => setRightTab("checks")}>Checks</button>
          <button type="button" role="tab" aria-selected={rightTab === "history"} onClick={() => setRightTab("history")}>History</button>
          <button type="button" role="tab" aria-selected={rightTab === "comments"} onClick={() => setRightTab("comments")}>
            Comments{Object.keys(x.commentCounts).length ? ` (${Object.values(x.commentCounts).reduce((a, b) => a + b, 0)})` : ""}
          </button>
        </div>
        {rightTab === "properties" && s.index ? (
          <>
            {selectedNodes.length > 1 ? (
              <p className={styles.panelBody} data-testid="vd-multi">{selectedNodes.length} items selected. Changes below apply to all of them.</p>
            ) : (
              <Inspector
                node={selected}
                index={s.index}
                onOp={addOp}
                compiled={s.compiled}
                showCode={s.showCode}
                onToggleCode={() => s.setShowCode(!s.showCode)}
              />
            )}
            {selected && selectedNodes.length === 1 && s.tree ? (
              <div className={styles.panelBody}>
                {selected.kind === "root" ? (
                  <ScreenSettings root={selected} {...extras} />
                ) : selected.tag === "field" ? (
                  <>
                    <FieldExtras node={selected} rootTag={s.tree.tag} {...extras} />
                    {selected.name ? (
                      <FieldDepsPanel
                        connectionId={connectionId}
                        model={s.model}
                        viewType={s.viewType}
                        viewId={s.viewId}
                        field={selected.name}
                        onJump={jump}
                        errorText={x.errorText}
                      />
                    ) : null}
                  </>
                ) : ["group", "page", "notebook"].includes(selected.tag) ? (
                  <SaveSection node={selected} {...extras} />
                ) : null}
              </div>
            ) : null}
            {selected && selectedNodes.length === 1 && s.tree ? (
              <div className={styles.panelBody}>
                <RulesPanel
                  key={`${selected.id}:${hideRuleFor === selected.id ? "hide" : "show"}`}
                  initialSense={hideRuleFor === selected.id ? "hide" : "show"}
                  connectionId={connectionId}
                  model={s.model}
                  rootTag={s.tree.tag}
                  node={selected}
                  fields={s.base?.fields ?? {}}
                  onOp={addOp}
                  errorText={x.errorText}
                />
              </div>
            ) : null}
            {selectedNodes.length && selectedNodes[0].kind !== "root" ? (
              <div className={styles.panelBody}>
                <WhoCanSeePanel
                  connectionId={connectionId}
                  model={s.model}
                  viewType={s.viewType}
                  ops={s.ops}
                  nodes={selectedNodes}
                  index={s.index}
                  roles={x.roles}
                  onOps={addOps}
                  onOpenRecordAccess={() => x.setAccessOpen(true)}
                  onUseRule={(id) => {
                    setHideRuleFor(id);
                    select(id);
                    setAnnounce("Pick when to hide it in the rules above");
                    toast("Pick when to hide it in the rules above.");
                  }}
                  errorText={x.errorText}
                />
              </div>
            ) : (
              <div className={styles.panelBody}>
                <Button size="sm" variant="ghost" onClick={() => x.setAccessOpen(true)}>Access to this record type…</Button>
              </div>
            )}
          </>
        ) : null}
        {rightTab === "checks" ? (
          <ChecksPanel
            connectionId={connectionId}
            model={s.model}
            viewType={s.viewType}
            viewId={s.viewId}
            ops={s.ops}
            onOps={addOps}
            onJump={jump}
            errorText={x.errorText}
          />
        ) : null}
        {rightTab === "history" ? (
          <HistoryPanel
            connectionId={connectionId}
            model={s.model}
            viewType={s.viewType}
            refreshKey={s.publishCount}
            onMarkers={x.setMarkers}
            onScrub={x.setScrub}
            onRestored={() => {
              x.setScrub(null);
              void s.reload();
            }}
            errorText={x.errorText}
          />
        ) : null}
        {rightTab === "comments" && s.index ? (
          <CommentsPanel
            connectionId={connectionId}
            model={s.model}
            viewType={s.viewType}
            nodeId={s.selectedId}
            index={s.index}
            comments={x.comments}
            onChanged={() => void x.reloadComments()}
            errorText={x.errorText}
          />
        ) : null}
      </aside>
      <BuilderSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        tab={sheetTab}
        onTab={setSheetTab}
        connectionId={connectionId}
        model={s.model}
        viewType={s.viewType}
        viewId={s.viewId}
        layerHash={s.base?.layer_hash ?? null}
        onOpenScreen={(vt, id) => {
          s.setSelectedId(null);
          s.setViewType(vt);
          s.setViewId(id);
          setSheetOpen(false);
        }}
        onChanged={() => void s.reload()}
        errorText={x.errorText}
      />
      <Builder2cSheet
        selectedNode={s.selectedId}
        onAddOps={(ops, label) => s.addOps(ops, label)}
        open={sheet2cOpen}
        onOpenChange={setSheet2cOpen}
        tab={sheet2cTab}
        onTab={setSheet2cTab}
        connectionId={connectionId}
        model={s.model}
        viewType={s.viewType}
        viewId={s.viewId}
        ops={s.ops}
        summary={s.index ? s.ops.map((o) => describeOp(o, s.index!, s.fieldLabel)) : []}
        layerHash={s.base?.layer_hash ?? null}
        roles={x.roles}
        fields={s.base?.fields ?? {}}
        heatOn={Boolean(z.heat)}
        onHeat={z.setHeat}
        sampleOn={Boolean(z.sample)}
        onSample={z.setSample}
        simulate={z.simulate}
        onSimulate={z.setSimulate}
        onTour={z.startTour}
        onJump={jump}
        onOpenScreen={(vt, id) => {
          s.setSelectedId(null);
          s.setViewType(vt);
          s.setViewId(id);
          setSheet2cOpen(false);
        }}
        onClearOps={s.clearOps}
        onChanged={() => void s.reload()}
        errorText={x.errorText}
      />
      <RecordAccessSheet open={x.accessOpen} onOpenChange={x.setAccessOpen} connectionId={connectionId} model={s.model} errorText={x.errorText} />
      <CommandBar
        open={x.commandOpen}
        onOpenChange={x.setCommandOpen}
        connectionId={connectionId}
        model={s.model}
        viewType={s.viewType}
        ops={s.ops}
        index={s.index}
        onJump={jump}
        onMarkers={x.setMarkers}
        onApply={addOps}
        errorText={x.errorText}
        actions={[
          { id: "publish", label: pending ? `Publish changes (${pending})` : "Publish changes", run: () => void s.publish() },
          { id: "undo", label: "Undo the last change", run: s.undo },
          { id: "code", label: s.showCode ? "Hide code" : "Show code", run: () => s.setShowCode(!s.showCode) },
          { id: "comments", label: x.commentsOn ? "Hide comments" : "Show comments", run: () => { x.setCommentsOn(!x.commentsOn); setRightTab("comments"); } },
          { id: "versions", label: "Compare Odoo versions side by side", run: () => x.setVersionsOpen(true) },
          { id: "history", label: "Open history", run: () => setRightTab("history") },
          { id: "access", label: "Access to this record type", run: () => x.setAccessOpen(true) },
          { id: "checks", label: "Check this screen (health score)", run: () => setRightTab("checks") },
          { id: "add", label: "Add fields and components", run: () => setLeftTab("add") },
          { id: "new-screen", label: "Make a new screen", run: () => openSheet("screen") },
          { id: "translate", label: "Translate labels", run: () => openSheet("translate") },
          { id: "guard", label: "Check changes against Odoo updates", run: () => openSheet("guard") },
          { id: "package", label: "Move this screen to production", run: () => openSheet("package") },
          { id: "tour", label: "Explain this screen (guided tour)", run: () => void api.explainScreen(connectionId, { model: s.model, view_type: s.viewType, view_id: s.viewId, ops: s.ops }).then((o) => z.startTour(o.steps)).catch((e) => toast.error(x.errorText(e))) },
          { id: "heatmap", label: z.heat ? "Hide usage heatmap" : "Show usage heatmap", run: () => (z.heat ? z.setHeat(null) : void api.heatmap(connectionId, { model: s.model, view_type: s.viewType, view_id: s.viewId, ops: s.ops }).then((o) => z.setHeat(o.heat)).catch((e) => toast.error(x.errorText(e)))) },
          { id: "blockers", label: "What blocks saving", run: () => open2c("insights") },
          { id: "a11y", label: "Accessibility check", run: () => open2c("insights") },
          { id: "steps", label: "Step-by-step mode for a role", run: () => open2c("roles") },
          { id: "abtest", label: "Test two layouts", run: () => open2c("roles") },
          { id: "dashboard", label: "Make a dashboard", run: () => open2c("dashboards") },
          { id: "starter", label: "Start from an industry screen", run: () => open2c("starters") },
          { id: "approval", label: "Ask for approval", run: () => open2c("publishing") },
          { id: "schedule", label: "Publish later", run: () => open2c("publishing") },
          { id: "digest", label: "Weekly digest", run: () => open2c("publishing") },
          ...DEVICES.map((d) => ({ id: `device-${d.id}`, label: `Preview on ${d.label.toLowerCase()}`, run: () => s.setDevice(d.id) })),
        ]}
      />
      <div className={styles.srOnly} aria-live="polite" data-testid="vd-live">{announce}</div>
    </div>
  );
}

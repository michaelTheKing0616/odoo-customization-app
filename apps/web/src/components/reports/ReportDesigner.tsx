"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
  advancedMutationAllowed,
  isExperimentalMajor,
} from "@/lib/capabilities";
import type { Connection } from "@/lib/api";
import {
  ReportBlock,
  ReportBlockType,
  ReportCanvas,
  ReportDesignSpec,
  reorderReportBlocks,
  setReportPaletteDragData,
} from "./ReportCanvas";
import {
  DEFAULT_INHERIT_SLOT,
  REPORT_INHERIT_SLOTS,
  ReportInheritOp,
  ReportInheritSlot,
  buildReportInheritOp,
  inheritAnchorForSlot,
  loadPersistedReportDesign,
  parseInheritSlotFromArch,
  persistReportDesign,
  reportInheritRootReplaceIssue,
} from "./reportInheritSlots";
import { ReportFieldPicker } from "./ReportFieldPicker";
import {
  DEFAULT_USE_EXTERNAL_LAYOUT,
  o2mFieldOptions,
  parentFieldOptions,
  refuseEmptyDesign,
  relationalLineFields,
  validateGroundedFields,
} from "./reportGrounding";
import { refuseUnsafeBlockText } from "./reportUnsafeGate";
import { ReportTableInspector } from "./ReportTableInspector";
import {
  normalizeTableBlockColumns,
  validateTableTotals,
} from "./reportTableColumns";
import {
  formatQwebRenderErrorDisplay,
  parseQwebRenderError,
} from "./reportRenderError";
import { Skeleton } from "@/components/ui/layout-primitives";
import { Button } from "@/components/ui/Button";
import type { FieldRow } from "@/lib/api";

type PaletteItem = { type: string; label: string; hint: string };

export type AvailableReportOption = {
  id: number;
  name: string;
  report_name: string | null;
  model?: string | null;
  arch?: string | null;
};

type ReportDesignerProps = {
  connectionId: string;
  model: string;
  reportKey: string;
  reportName: string;
  reportId: number | null;
  paperLabel?: string;
  connection?: Connection | null;
  /** Existing ir.actions.report rows on the connection (base picker). */
  availableReports?: AvailableReportOption[];
  /** Latest compiled arch from the parent (used for round-trip slot restore). */
  initialArch?: string | null;
  onArchChange: (arch: string) => void;
  /** Fires whenever the inherit save payload changes (null in primary mode). */
  onInheritOpChange?: (op: ReportInheritOp | null) => void;
  /** Fires the validated save payload; parent persists arch / op. */
  onEmitSave?: (payload: {
    mode: "primary" | "inherit";
    arch: string;
    spec: ReportDesignSpec;
    op: ReportInheritOp | null;
  }) => void | Promise<void>;
  onNotice?: (msg: string) => void;
  onError?: (msg: string) => void;
};

function newBlock(type: ReportBlockType): ReportBlock {
  const id = `b_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
  switch (type) {
    case "heading":
      return { id, type, text: "Section", level: 2 };
    case "field":
      return { id, type, field: "display_name" };
    case "label_field":
      return { id, type, label: "Label", field: "display_name" };
    case "o2m_table":
      return {
        id,
        type,
        o2m_field: "line_ids",
        columns: [{ field: "name", label: "Description" }],
      };
    case "image":
      return { id, type, image_src: "company_logo" };
    case "divider":
      return { id, type };
    case "page_break":
      return { id, type };
    default:
      return { id, type: "text", text: "Paragraph text" };
  }
}

function isReportBlock(value: unknown): value is ReportBlock {
  return (
    !!value &&
    typeof value === "object" &&
    typeof (value as ReportBlock).id === "string" &&
    typeof (value as ReportBlock).type === "string"
  );
}

export function ReportDesigner({
  connectionId,
  model,
  reportKey,
  reportName,
  reportId,
  paperLabel,
  connection = null,
  availableReports = [],
  initialArch = null,
  onArchChange,
  onInheritOpChange,
  onEmitSave,
  onNotice,
  onError,
}: ReportDesignerProps) {
  const [palette, setPalette] = useState<PaletteItem[]>([]);
  const [blocks, setBlocks] = useState<ReportBlock[]>([
    { id: "h1", type: "heading", text: "Document", level: 1 },
    { id: "f1", type: "field", field: "display_name" },
  ]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  /** PDF-07: Table Inspector focus (column index within the selected table). */
  const [activeColumn, setActiveColumn] = useState<{ blockId: string; index: number } | null>(
    null,
  );
  const [useExternalLayout, setUseExternalLayout] = useState(DEFAULT_USE_EXTERNAL_LAYOUT);
  const [tLang, setTLang] = useState("");
  const [mode, setMode] = useState<"primary" | "inherit">("primary");
  const [inheritBase, setInheritBase] = useState("");
  const [inheritSlot, setInheritSlot] =
    useState<ReportInheritSlot>(DEFAULT_INHERIT_SLOT);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewRecordId, setPreviewRecordId] = useState("1");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [hydratedKey, setHydratedKey] = useState<string | null>(null);
  const [modelFields, setModelFields] = useState<FieldRow[]>([]);
  const [relatedByO2m, setRelatedByO2m] = useState<Record<string, FieldRow[]>>({});
  const [fieldsError, setFieldsError] = useState<string | null>(null);

  const selected = blocks.find((b) => b.id === selectedId) ?? null;
  const inheritAnchor = inheritAnchorForSlot(inheritSlot);

  const availableReportKeys = useMemo(
    () =>
      availableReports
        .map((r) => (r.report_name || "").trim())
        .filter(Boolean),
    [availableReports],
  );

  const parentFieldsSorted = useMemo(
    () => parentFieldOptions(modelFields),
    [modelFields],
  );
  const o2mOptions = useMemo(() => o2mFieldOptions(modelFields), [modelFields]);
  const parentFieldNames = useMemo(
    () => new Set(modelFields.map((f) => f.name)),
    [modelFields],
  );
  const lineRelations = useMemo(
    () => relationalLineFields(modelFields),
    [modelFields],
  );
  const relatedNameSets = useMemo(() => {
    const out = new Map<string, Set<string>>();
    for (const [o2m, rows] of Object.entries(relatedByO2m)) {
      out.set(o2m, new Set(rows.map((f) => f.name)));
    }
    return out;
  }, [relatedByO2m]);

  const selectedRelatedFields = useMemo(() => {
    if (selected?.type !== "o2m_table") return [] as FieldRow[];
    const key = (selected.o2m_field || selected.field || "").trim();
    return key ? relatedByO2m[key] || [] : [];
  }, [relatedByO2m, selected]);

  const relatedTypeMaps = useMemo(() => {
    const out = new Map<string, Map<string, string>>();
    for (const [o2m, rows] of Object.entries(relatedByO2m)) {
      if (!rows.length) continue;
      out.set(o2m, new Map(rows.map((f) => [f.name, f.ttype])));
    }
    return out;
  }, [relatedByO2m]);

  // Canvas mirrors the compiler: column ttype comes from the related schema
  // (the API re-annotates the same way), so numeric defaults align right.
  const canvasBlocks = useMemo(
    () =>
      blocks.map((b) => {
        if (b.type !== "o2m_table" || !b.columns?.length) return b;
        const types = relatedTypeMaps.get((b.o2m_field || b.field || "").trim());
        if (!types) return b;
        return {
          ...b,
          columns: b.columns.map((c) =>
            types.has(c.field) ? { ...c, ttype: types.get(c.field) } : c,
          ),
        };
      }),
    [blocks, relatedTypeMaps],
  );

  const activeColumnIndex =
    selected?.type === "o2m_table" && activeColumn?.blockId === selected.id
      ? activeColumn.index
      : 0;

  const experimental = isExperimentalMajor(connection?.capabilities);
  const canApplyToProduction = advancedMutationAllowed(connection);

  const spec: ReportDesignSpec = useMemo(
    () => ({
      name: reportName,
      model,
      report_key: reportKey,
      use_external_layout: useExternalLayout,
      t_lang: tLang.trim() || null,
      mode,
      inherit:
        mode === "inherit"
          ? {
              base_report_key: inheritBase,
              slot: inheritSlot,
              xpath: inheritAnchor.xpath,
              position: inheritAnchor.position,
            }
          : undefined,
      blocks,
    }),
    [
      blocks,
      inheritAnchor.position,
      inheritAnchor.xpath,
      inheritBase,
      inheritSlot,
      mode,
      model,
      reportKey,
      reportName,
      tLang,
      useExternalLayout,
    ],
  );

  const compile = useCallback(async () => {
    const payload =
      mode === "inherit"
        ? { ...spec, available_report_keys: availableReportKeys }
        : spec;
    const res = await api.compileReportDesign(connectionId, { spec: payload });
    onArchChange(res.arch);
    return res.arch;
  }, [availableReportKeys, connectionId, mode, onArchChange, spec]);

  // Round-trip: restore slot + blocks from localStorage, then arch.
  useEffect(() => {
    const key = `${connectionId}::${reportKey}`;
    if (hydratedKey === key) return;
    const persisted = loadPersistedReportDesign(connectionId, reportKey);
    if (persisted) {
      setMode(persisted.mode);
      if (persisted.mode === "inherit") {
        if (persisted.inheritSlot) setInheritSlot(persisted.inheritSlot);
        if (persisted.inheritBase) setInheritBase(persisted.inheritBase);
      }
      if (Array.isArray(persisted.blocks)) {
        setBlocks(persisted.blocks.filter(isReportBlock).map(normalizeTableBlockColumns));
      }
      if (typeof persisted.useExternalLayout === "boolean") {
        setUseExternalLayout(persisted.useExternalLayout);
      }
      if (typeof persisted.tLang === "string") setTLang(persisted.tLang);
      setHydratedKey(key);
      return;
    }
    if (initialArch) {
      const parsed = parseInheritSlotFromArch(initialArch);
      if (parsed.baseReportKey || parsed.slot) {
        setMode("inherit");
        if (parsed.baseReportKey) setInheritBase(parsed.baseReportKey);
        if (parsed.slot) setInheritSlot(parsed.slot);
      }
    }
    setHydratedKey(key);
  }, [connectionId, reportKey, initialArch, hydratedKey]);

  useEffect(() => {
    api
      .getReportDesignPalette(connectionId)
      .then(setPalette)
      .catch(() =>
        setPalette([
          { type: "heading", label: "Heading", hint: "" },
          { type: "field", label: "Field", hint: "" },
        ]),
      );
  }, [connectionId]);

  // PDF-04: schema client — listFields == fields_get for the bound model.
  useEffect(() => {
    let cancelled = false;
    setFieldsError(null);
    if (!model.trim()) {
      setModelFields([]);
      return;
    }
    api
      .listFields(connectionId, model)
      .then((rows) => {
        if (!cancelled) setModelFields(rows);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setModelFields([]);
          setFieldsError(err.message || "Failed to load model fields");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, model]);

  // Line-table columns only from each related comodel's fields_get.
  useEffect(() => {
    let cancelled = false;
    const o2mNames = Array.from(
      new Set(
        blocks
          .filter((b) => b.type === "o2m_table")
          .map((b) => (b.o2m_field || b.field || "").trim())
          .filter(Boolean),
      ),
    );
    if (!o2mNames.length || !lineRelations.size) {
      return;
    }
    void (async () => {
      const next: Record<string, FieldRow[]> = {};
      for (const o2m of o2mNames) {
        const comodel = lineRelations.get(o2m);
        if (!comodel) {
          next[o2m] = [];
          continue;
        }
        try {
          next[o2m] = await api.listFields(connectionId, comodel);
        } catch {
          next[o2m] = [];
        }
      }
      if (!cancelled) setRelatedByO2m((prev) => ({ ...prev, ...next }));
    })();
    return () => {
      cancelled = true;
    };
  }, [blocks, connectionId, lineRelations]);

  useEffect(() => {
    compile().catch(() => {});
  }, [compile]);

  // Keep parent informed of the current inherit op (one anchor).
  useEffect(() => {
    if (!onInheritOpChange) return;
    if (mode !== "inherit") {
      onInheritOpChange(null);
      return;
    }
    const built = buildReportInheritOp({
      baseReportKey: inheritBase,
      slot: inheritSlot,
      availableReportKeys,
      model,
      name: `${reportName} inherit`,
    });
    onInheritOpChange(built.ok ? built.op : null);
  }, [
    availableReportKeys,
    inheritBase,
    inheritSlot,
    mode,
    model,
    onInheritOpChange,
    reportName,
  ]);

  function moveBlock(id: string, dir: -1 | 1) {
    setBlocks((prev) => {
      const idx = prev.findIndex((b) => b.id === id);
      if (idx < 0) return prev;
      const next = idx + dir;
      if (next < 0 || next >= prev.length) return prev;
      const copy = [...prev];
      const [item] = copy.splice(idx, 1);
      copy.splice(next, 0, item);
      return copy;
    });
  }

  function reorderBlocks(fromIndex: number, toIndex: number) {
    setBlocks((prev) => reorderReportBlocks(prev, fromIndex, toIndex));
  }

  function insertBlockAt(type: ReportBlockType, insertIndex: number) {
    const block = newBlock(type);
    setBlocks((prev) => {
      const i = Math.max(0, Math.min(insertIndex, prev.length));
      const next = prev.slice();
      next.splice(i, 0, block);
      return next;
    });
    selectBlock(block.id);
  }

  function selectBlock(id: string) {
    setSelectedId(id);
    // Keep the inspector's column focus when re-selecting the same table.
    setActiveColumn((prev) => (prev?.blockId === id ? prev : { blockId: id, index: 0 }));
  }

  function selectTableColumn(blockId: string, index: number) {
    setSelectedId(blockId);
    setActiveColumn({ blockId, index });
  }

  function updateSelected(patch: Partial<ReportBlock>) {
    if (!selectedId) return;
    setBlocks((prev) =>
      prev.map((b) => (b.id === selectedId ? { ...b, ...patch } : b)),
    );
  }

  function persistCurrentDesign() {
    persistReportDesign(connectionId, reportKey, {
      mode,
      inheritSlot: mode === "inherit" ? inheritSlot : undefined,
      inheritBase: mode === "inherit" ? inheritBase : undefined,
      blocks,
      useExternalLayout,
      tLang,
    });
  }

  async function onPreview() {
    if (!reportId) {
      onError?.("Select or create a report first, then preview.");
      return;
    }
    setBusy(true);
    setPreviewLoading(true);
    setRenderError(null);
    try {
      const unsafePreviewErr = refuseUnsafeBlockText(blocks);
      if (unsafePreviewErr) {
        onError?.(unsafePreviewErr);
        return;
      }
      await compile();
      const res = await api.previewReportDesign(connectionId, {
        spec,
        report_id: reportId,
        record_id: Number(previewRecordId) || 1,
      });
      const bin = Uint8Array.from(atob(res.content_base64), (c) => c.charCodeAt(0));
      const blob = new Blob([bin], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(url);
      onNotice?.(`Preview via ${res.render_path}`);
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Preview failed";
      setRenderError(raw);
      onError?.(formatQwebRenderErrorDisplay(raw));
    } finally {
      setPreviewLoading(false);
      setBusy(false);
    }
  }

  async function onExportModuleFragment() {
    setBusy(true);
    try {
      const res = await api.reportDesignToModuleSpec(connectionId, { spec });
      const blob = new Blob([JSON.stringify(res.fragment, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${reportKey.replace(/\./g, "_")}_report_fragment.json`;
      a.click();
      URL.revokeObjectURL(url);
      onNotice?.("App plan report fragment downloaded");
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSavePrintout() {
    setBusy(true);
    try {
      if (mode === "inherit") {
        const rt22 = reportInheritRootReplaceIssue({
          xpath: inheritAnchor.xpath,
          position: inheritAnchor.position,
        });
        if (rt22) {
          onError?.(rt22);
          return;
        }
        const built = buildReportInheritOp({
          baseReportKey: inheritBase,
          slot: inheritSlot,
          availableReportKeys,
          model,
          name: `${reportName} inherit`,
        });
        if (!built.ok) {
          onError?.(built.error);
          return;
        }
        const unsafeInheritErr = refuseUnsafeBlockText(blocks);
        if (unsafeInheritErr) {
          onError?.(unsafeInheritErr);
          return;
        }
        const arch = await compile();
        const op: ReportInheritOp = {
          ...built.op,
          params: { ...built.op.params, arch },
        };
        persistCurrentDesign();
        await onEmitSave?.({ mode, arch, spec, op });
        onInheritOpChange?.(op);
        onNotice?.(
          `Saved report.inherit (${op.params.slot} → ${op.params.xpath} ${op.params.position})`,
        );
        return;
      }
      const emptyErr = refuseEmptyDesign(spec);
      if (emptyErr) {
        onError?.(emptyErr);
        return;
      }
      const unsafeBlockErr = refuseUnsafeBlockText(blocks);
      if (unsafeBlockErr) {
        onError?.(unsafeBlockErr);
        return;
      }
      if (parentFieldNames.size > 0) {
        const groundErr = validateGroundedFields(
          blocks,
          parentFieldNames,
          relatedNameSets,
        );
        if (groundErr) {
          onError?.(groundErr);
          return;
        }
      }
      const totalsErr = validateTableTotals(blocks, relatedTypeMaps);
      if (totalsErr) {
        onError?.(totalsErr);
        return;
      }
      const arch = await compile();
      persistCurrentDesign();
      await onEmitSave?.({ mode, arch, spec, op: null });
      onNotice?.("Saved printout");
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  const renderErrorInfo = renderError ? parseQwebRenderError(renderError) : null;

  return (
    <div className="grid gap-3 lg:grid-cols-[188px_1fr_240px]">
      <aside className="space-y-1.5 rounded-lg border border-[color-mix(in_srgb,var(--ink,#1a1c21)_10%,transparent)] bg-[color-mix(in_srgb,var(--surface-raised,#fff)_40%,transparent)] p-2.5 text-sm">
        <h3 className="px-0.5 text-[0.6875rem] font-medium tracking-wide text-muted">Blocks</h3>
        {palette.map((p) => (
          <button
            key={p.type}
            type="button"
            title={p.hint || "Drag onto the page, or click to append"}
            disabled={busy}
            draggable={!busy}
            data-testid={`report-palette-${p.type}`}
            onDragStart={(e) => {
              setReportPaletteDragData(e.dataTransfer, p.type);
            }}
            onClick={() => insertBlockAt(p.type as ReportBlockType, blocks.length)}
            className="block w-full rounded-md border border-transparent px-2 py-1.5 text-left text-xs text-ink hover:bg-surface-raised"
          >
            + {p.label}
          </button>
        ))}
        <p className="pt-2 text-xs text-muted">
          t-lang: set partner language field below; see Config → ModuleSpec translations for
          label CSV round-trip.
        </p>
      </aside>

      <div>
        <ReportCanvas
          blocks={canvasBlocks}
          paperLabel={paperLabel}
          useExternalLayout={useExternalLayout}
          selectedId={selectedId}
          onSelect={selectBlock}
          activeColumn={
            selected?.type === "o2m_table"
              ? { blockId: selected.id, index: activeColumnIndex }
              : null
          }
          onSelectColumn={selectTableColumn}
          onMove={moveBlock}
          onReorder={reorderBlocks}
          onInsertBlock={insertBlockAt}
          onAddBlock={() => insertBlockAt("text", blocks.length)}
          documentTitle={reportName}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => compile().then(() => onNotice?.("QWeb synced to Code tab"))}
            className="border border-border-subtle px-3 py-1 text-sm text-muted"
          >
            Sync QWeb
          </button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={busy}
            data-testid="report-save-printout"
            onClick={() => void onSavePrintout()}
          >
            Save the printout
          </Button>
          <input
            value={previewRecordId}
            onChange={(e) => setPreviewRecordId(e.target.value)}
            className="w-20 border border-border-subtle bg-surface px-2 py-1 font-mono text-xs"
            placeholder="rec id"
          />
          <button
            type="button"
            disabled={busy || !reportId}
            onClick={() => void onPreview()}
            className="border border-border-subtle px-3 py-1 text-sm text-muted"
          >
            Live PDF preview
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void onExportModuleFragment()}
            className="border border-border-subtle px-3 py-1 text-sm text-muted"
          >
            Export ModuleSpec fragment
          </button>
          {canApplyToProduction ? (
            <button
              type="button"
              disabled={busy}
              data-testid="report-apply-to-production"
              title="Sandbox-render before promoting to a production connection"
              onClick={() =>
                onNotice?.(
                  "Apply to production stays a human promote step after sandbox render.",
                )
              }
              className="border border-border-subtle px-3 py-1 text-sm text-muted"
            >
              Apply to production
            </button>
          ) : null}
        </div>
        {experimental ? (
          <p
            className="mt-2 text-xs text-muted"
            data-testid="report-odoo16-experimental-caveat"
          >
            Odoo {connection?.capabilities?.major ?? 16} is experimental for QWeb
            reports — verify in Open-in-Odoo after create. Apply to production is
            not offered on experimental majors.
          </p>
        ) : null}
        {previewLoading ? (
          <div
            className="mt-4 space-y-2 rounded-md border border-border-subtle bg-surface-raised p-3"
            data-testid="report-preview-loading"
            aria-busy="true"
            aria-live="polite"
          >
            <p className="text-xs font-medium text-muted">Rendering PDF preview…</p>
            <Skeleton className="h-3 w-40" />
            <Skeleton className="h-96 w-full" />
          </div>
        ) : null}
        {renderErrorInfo ? (
          <div
            role="alert"
            data-testid="report-render-error"
            className="mt-4 rounded-md border border-danger/30 bg-danger-subtle p-3 text-sm text-ink"
          >
            <p className="font-semibold text-danger">{renderErrorInfo.summary}</p>
            {renderErrorInfo.templateLine != null ? (
              <p
                className="mt-1 font-mono text-xs tabular-nums text-muted"
                data-testid="report-render-error-line"
              >
                Template line {renderErrorInfo.templateLine}
              </p>
            ) : null}
            <p className="mt-2 text-pretty text-xs text-muted">{renderErrorInfo.message}</p>
          </div>
        ) : null}
        {previewUrl && !previewLoading ? (
          <iframe
            title="Report preview"
            src={previewUrl}
            data-testid="report-preview-frame"
            className="mt-4 h-96 w-full border border-border-subtle bg-surface"
          />
        ) : null}
      </div>

      <aside className="space-y-3 rounded-lg border border-[color-mix(in_srgb,var(--ink,#1a1c21)_10%,transparent)] bg-[color-mix(in_srgb,var(--surface-raised,#fff)_40%,transparent)] p-2.5 text-sm">
        <h3 className="px-0.5 text-[0.6875rem] font-medium tracking-wide text-muted">Layout</h3>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={useExternalLayout}
            onChange={(e) => setUseExternalLayout(e.target.checked)}
          />
          web.external_layout
        </label>
        <label className="block text-xs">
          <span className="text-muted">t-lang (optional)</span>
          <input
            value={tLang}
            onChange={(e) => setTLang(e.target.value)}
            placeholder="o.partner_id.lang"
            className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 font-mono text-xs"
          />
        </label>
        <label className="block text-xs">
          <span className="text-muted">Mode</span>
          <select
            value={mode}
            data-testid="report-mode-select"
            onChange={(e) => setMode(e.target.value as "primary" | "inherit")}
            className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1"
          >
            <option value="primary">New report</option>
            <option value="inherit">Inherit existing</option>
          </select>
        </label>
        {mode === "inherit" && (
          <div
            className="space-y-3 rounded-lg border border-[color-mix(in_srgb,var(--ink,#1a1c21)_10%,transparent)] bg-[color-mix(in_srgb,var(--surface-raised,#fff)_55%,transparent)] p-3"
            data-testid="report-inherit-chrome"
          >
            <div>
              <p className="text-[0.6875rem] font-medium tracking-[-0.01em] text-ink">
                Extend one slot
              </p>
              <p className="mt-1 text-[11px] text-pretty leading-snug text-muted">
                Stock body stays intact. One anchor only — no raw XPath editor.
              </p>
            </div>
            <label className="block text-xs">
              <span className="text-muted">Base report</span>
              <select
                value={inheritBase}
                data-testid="report-inherit-base-select"
                onChange={(e) => setInheritBase(e.target.value)}
                className="mt-1 w-full rounded-md border border-border-subtle bg-surface px-2 py-1.5 font-mono text-xs"
              >
                <option value="">— pick existing ir.actions.report —</option>
                {availableReports.map((r) => {
                  const key = (r.report_name || "").trim();
                  if (!key) return null;
                  return (
                    <option key={r.id} value={key}>
                      {r.name} ({key})
                    </option>
                  );
                })}
              </select>
            </label>
            <fieldset className="space-y-1.5" data-testid="report-inherit-slot-picker">
              <legend className="text-xs text-muted">Slot</legend>
              <div className="grid grid-cols-1 gap-1">
                {REPORT_INHERIT_SLOTS.map((entry) => {
                  const on = inheritSlot === entry.slot;
                  return (
                    <label
                      key={entry.slot}
                      className={
                        on
                          ? "flex cursor-pointer items-start gap-2 rounded-md border border-accent/40 bg-surface-raised px-2 py-1.5 text-xs"
                          : "flex cursor-pointer items-start gap-2 rounded-md border border-transparent px-2 py-1.5 text-xs hover:bg-surface-raised/70"
                      }
                    >
                      <input
                        type="radio"
                        name="report-inherit-slot"
                        value={entry.slot}
                        checked={on}
                        data-testid={`report-inherit-slot-${entry.slot}`}
                        onChange={() => setInheritSlot(entry.slot)}
                        className="mt-0.5"
                      />
                      <span>
                        <span className="font-medium text-ink">{entry.label}</span>
                        <span className="block text-[10px] leading-snug text-muted">
                          {entry.hint}
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
              <p className="pt-1 font-mono text-[10px] text-muted" data-testid="report-inherit-anchor-preview">
                {inheritAnchor.xpath} · {inheritAnchor.position}
              </p>
            </fieldset>
          </div>
        )}
        {selected && (
          <>
            <h3 className="font-semibold text-muted">Block</h3>
            {(selected.type === "heading" || selected.type === "text") && (
              <label className="block text-xs">
                Text
                <input
                  value={selected.text || ""}
                  onChange={(e) => updateSelected({ text: e.target.value })}
                  className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1"
                />
              </label>
            )}
            {(selected.type === "field" || selected.type === "label_field") && (
              <ReportFieldPicker
                label="Field"
                testId="report-field-picker"
                value={selected.field || ""}
                fields={parentFieldsSorted}
                onChange={(v) => updateSelected({ field: v })}
              />
            )}
            {selected.type === "image" && (
              <ReportFieldPicker
                label="Image field"
                testId="report-image-field-picker"
                value={selected.image_src || selected.field || "company_logo"}
                fields={parentFieldsSorted}
                extraOptions={[
                  { value: "company_logo", label: "company_logo (company logo)" },
                ]}
                onChange={(v) =>
                  updateSelected({ image_src: v, field: v })
                }
              />
            )}
            {selected.type === "label_field" && (
              <label className="block text-xs">
                Label
                <input
                  value={selected.label || ""}
                  onChange={(e) => updateSelected({ label: e.target.value })}
                  className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1"
                />
              </label>
            )}
            {selected.type === "o2m_table" && (
              <ReportTableInspector
                block={selected}
                o2mOptions={o2mOptions}
                relatedFields={selectedRelatedFields}
                activeIndex={activeColumnIndex}
                disabled={busy}
                onActiveIndexChange={(index) =>
                  setActiveColumn({ blockId: selected.id, index })
                }
                onChange={updateSelected}
              />
            )}
            {fieldsError ? (
              <p className="text-[10px] text-danger" data-testid="report-fields-error">
                {fieldsError}
              </p>
            ) : null}
            <button
              type="button"
              className="text-xs text-danger"
              onClick={() => {
                setBlocks((prev) => prev.filter((b) => b.id !== selectedId));
                setSelectedId(null);
              }}
            >
              Remove block
            </button>
          </>
        )}
      </aside>
    </div>
  );
}

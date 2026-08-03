"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
  RENTAL_AGREEMENT_STARTER,
  ReportBlock,
  ReportBlockType,
  ReportCanvas,
  ReportDesignSpec,
} from "./ReportCanvas";

type PaletteItem = { type: string; label: string; hint: string };

type ReportDesignerProps = {
  connectionId: string;
  model: string;
  reportKey: string;
  reportName: string;
  reportId: number | null;
  paperLabel?: string;
  onArchChange: (arch: string) => void;
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

export function ReportDesigner({
  connectionId,
  model,
  reportKey,
  reportName,
  reportId,
  paperLabel,
  onArchChange,
  onNotice,
  onError,
}: ReportDesignerProps) {
  const [palette, setPalette] = useState<PaletteItem[]>([]);
  const [blocks, setBlocks] = useState<ReportBlock[]>(RENTAL_AGREEMENT_STARTER);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [useExternalLayout, setUseExternalLayout] = useState(true);
  const [tLang, setTLang] = useState("");
  const [mode, setMode] = useState<"primary" | "inherit">("primary");
  const [inheritBase, setInheritBase] = useState("");
  const [inheritXpath, setInheritXpath] = useState("//div[@class='page']");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewRecordId, setPreviewRecordId] = useState("1");
  const [busy, setBusy] = useState(false);

  const selected = blocks.find((b) => b.id === selectedId) ?? null;

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
              xpath: inheritXpath,
              position: "inside",
            }
          : undefined,
      blocks,
    }),
    [
      blocks,
      inheritBase,
      inheritXpath,
      mode,
      model,
      reportKey,
      reportName,
      tLang,
      useExternalLayout,
    ],
  );

  const compile = useCallback(async () => {
    const res = await api.compileReportDesign(connectionId, { spec });
    onArchChange(res.arch);
    return res.arch;
  }, [connectionId, onArchChange, spec]);

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

  useEffect(() => {
    compile().catch(() => {});
  }, [compile]);

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

  function updateSelected(patch: Partial<ReportBlock>) {
    if (!selectedId) return;
    setBlocks((prev) =>
      prev.map((b) => (b.id === selectedId ? { ...b, ...patch } : b)),
    );
  }

  async function onPreview() {
    if (!reportId) {
      onError?.("Select or create a report first, then preview.");
      return;
    }
    setBusy(true);
    try {
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
      onError?.(err instanceof Error ? err.message : "Preview failed");
    } finally {
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
      onNotice?.("ModuleSpec report fragment downloaded");
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[200px_1fr_220px]">
      <aside className="space-y-2 border border-[#3d2a38] p-3 text-sm">
        <h3 className="font-semibold text-[#c9a9c0]">Blocks</h3>
        {palette.map((p) => (
          <button
            key={p.type}
            type="button"
            title={p.hint}
            disabled={busy}
            onClick={() => setBlocks((prev) => [...prev, newBlock(p.type as ReportBlockType)])}
            className="block w-full border border-[#3d2a38] px-2 py-1 text-left text-xs hover:bg-[#1a1218]"
          >
            + {p.label}
          </button>
        ))}
        <p className="pt-2 text-xs text-[#8f7a88]">
          t-lang: set partner language field below; see Config → ModuleSpec translations for
          label CSV round-trip.
        </p>
      </aside>

      <div>
        <ReportCanvas
          blocks={blocks}
          paperLabel={paperLabel}
          useExternalLayout={useExternalLayout}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onMove={moveBlock}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => compile().then(() => onNotice?.("QWeb synced to Code tab"))}
            className="border border-[#c9a9c0] px-3 py-1 text-sm text-[#c9a9c0]"
          >
            Sync QWeb
          </button>
          <input
            value={previewRecordId}
            onChange={(e) => setPreviewRecordId(e.target.value)}
            className="w-20 border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono text-xs"
            placeholder="rec id"
          />
          <button
            type="button"
            disabled={busy || !reportId}
            onClick={() => void onPreview()}
            className="border border-[#c9a9c0] px-3 py-1 text-sm text-[#c9a9c0]"
          >
            Live PDF preview
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void onExportModuleFragment()}
            className="border border-[#8f7a88] px-3 py-1 text-sm text-[#8f7a88]"
          >
            Export ModuleSpec fragment
          </button>
        </div>
        {previewUrl && (
          <iframe
            title="Report preview"
            src={previewUrl}
            className="mt-4 h-96 w-full border border-[#3d2a38] bg-white"
          />
        )}
      </div>

      <aside className="space-y-3 border border-[#3d2a38] p-3 text-sm">
        <h3 className="font-semibold text-[#c9a9c0]">Layout</h3>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={useExternalLayout}
            onChange={(e) => setUseExternalLayout(e.target.checked)}
          />
          web.external_layout
        </label>
        <label className="block text-xs">
          <span className="text-[#a8909e]">t-lang (optional)</span>
          <input
            value={tLang}
            onChange={(e) => setTLang(e.target.value)}
            placeholder="o.partner_id.lang"
            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono text-xs"
          />
        </label>
        <label className="block text-xs">
          <span className="text-[#a8909e]">Mode</span>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as "primary" | "inherit")}
            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1"
          >
            <option value="primary">New report</option>
            <option value="inherit">Inherit existing</option>
          </select>
        </label>
        {mode === "inherit" && (
          <>
            <label className="block text-xs">
              <span className="text-[#a8909e]">Base report key</span>
              <input
                value={inheritBase}
                onChange={(e) => setInheritBase(e.target.value)}
                placeholder="account.report_invoice"
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono text-xs"
              />
            </label>
            <label className="block text-xs">
              <span className="text-[#a8909e]">XPath anchor</span>
              <input
                value={inheritXpath}
                onChange={(e) => setInheritXpath(e.target.value)}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono text-xs"
              />
            </label>
          </>
        )}
        {selected && (
          <>
            <h3 className="font-semibold text-[#c9a9c0]">Block</h3>
            {(selected.type === "heading" || selected.type === "text") && (
              <label className="block text-xs">
                Text
                <input
                  value={selected.text || ""}
                  onChange={(e) => updateSelected({ text: e.target.value })}
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1"
                />
              </label>
            )}
            {(selected.type === "field" ||
              selected.type === "label_field" ||
              selected.type === "image") && (
              <label className="block text-xs">
                Field
                <input
                  value={selected.field || selected.image_src || ""}
                  onChange={(e) =>
                    updateSelected(
                      selected.type === "image"
                        ? { image_src: e.target.value, field: e.target.value }
                        : { field: e.target.value },
                    )
                  }
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono"
                />
              </label>
            )}
            {selected.type === "label_field" && (
              <label className="block text-xs">
                Label
                <input
                  value={selected.label || ""}
                  onChange={(e) => updateSelected({ label: e.target.value })}
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1"
                />
              </label>
            )}
            {selected.type === "o2m_table" && (
              <label className="block text-xs">
                O2M field
                <input
                  value={selected.o2m_field || ""}
                  onChange={(e) => updateSelected({ o2m_field: e.target.value })}
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono"
                />
              </label>
            )}
            <button
              type="button"
              className="text-xs text-[#f0a8a0]"
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

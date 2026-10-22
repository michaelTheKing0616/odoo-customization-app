"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { ReportLoadOut } from "@/lib/api/view-engine";
import type { CompareOut2b, LayoutLoadOut, VisualCompareOut, LayoutPublishOut, PageCheck, Placement, VariantsOut } from "@/lib/api/view-engine-2b";
import { blockCount, pdfUrlFromB64 } from "@/lib/viewDesigner2b";
import { blockReady, type FieldOpt } from "./BlockEditor";
import { noteWriteRefusal } from "../view-designer/writeModeSignal";
import { isNetworkError } from "../view-designer/useViewDesigner";

export type Variant = { key: string; label: string; lang: string | null; companyId: number | null; recordId: number | null };

const msg = (err: unknown, fallback: string) => {
  noteWriteRefusal(err);
  return err instanceof Error && err.message ? err.message : fallback;
};

/** Report Designer state (stage 2b): blocks in any safe place, real drafts from Odoo, checks, compare, publish. */
export function useReportDesigner(connectionId: string, initialModel = "account.move") {
  const [model, setModel] = useState(initialModel);
  const [reportId, setReportId] = useState<number | null>(null);
  const [data, setData] = useState<ReportLoadOut | null>(null);
  const [layout, setLayout] = useState<LayoutLoadOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [recordId, setRecordId] = useState<number | null>(null);
  const [slot, setSlot] = useState("bottom");
  const [placements, setPlacements] = useState<Placement[]>([]);
  const [saved, setSaved] = useState<Placement[]>([]);
  const [variants, setVariants] = useState<VariantsOut | null>(null);
  const [variant, setVariant] = useState<Variant | null>(null);
  const [proofUrl, setProofUrl] = useState<string | null>(null);
  const [proofPages, setProofPages] = useState<number | null>(null);
  const [publishedPages, setPublishedPages] = useState<number | null>(null);
  const [checks, setChecks] = useState<PageCheck[]>([]);
  const [proofing, setProofing] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [lastPublish, setLastPublish] = useState<LayoutPublishOut | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [draftNote, setDraftNote] = useState<string | null>(null);
  const [isDraft, setIsDraft] = useState(false);
  const [compare, setCompare] = useState<{ out: CompareOut2b; before: string; after: string } | null>(null);
  const [comparing, setComparing] = useState(false);
  const draftAbort = useRef<AbortController | null>(null);

  const showPdf = (b64: string) => setProofUrl(pdfUrlFromB64(b64));
  // Offline: keep the last layout on view, read-only, with Retry (same as View Designer).
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const sync = () => setOffline(!navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const out = await api.reportEngineLoad(connectionId, model, reportId);
      setOffline(false);
      setData(out);
      setRecordId((cur) => (cur && out.records.some((r) => r.id === cur) ? cur : out.records[0]?.id ?? null));
      if (out.report && out.report.id !== reportId) {
        setReportId(out.report.id);
        return; // the effect reloads with the chosen report
      }
      if (!out.report) {
        setLayout(null);
        return;
      }
      const lay = await api.layoutLoad(connectionId, out.report.id);
      setLayout(lay);
      const current = lay.placements ?? [];
      setPlacements(current);
      setSaved(current);
      setSlot((cur) => (lay.slots.some((s) => s.id === cur) ? cur : lay.slots.find((s) => s.id === "bottom")?.id ?? lay.slots[0]?.id ?? "bottom"));
      api.variants(connectionId, out.report.id).then(setVariants).catch(() => setVariants(null));
    } catch (err) {
      if (isNetworkError(err)) {
        setOffline(true); // keep the last layout on view; nothing was changed
        return;
      }
      setData(null);
      setLayout(null);
      setLoadError(msg(err, "Can't open this print layout."));
    } finally {
      setLoading(false);
    }
  }, [connectionId, model, reportId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => () => {
    if (proofUrl) URL.revokeObjectURL(proofUrl);
  }, [proofUrl]);

  const effectiveRecord = variant?.recordId ?? recordId;

  const showProof = useCallback(async () => {
    if (!reportId || !effectiveRecord) return;
    setProofing(true);
    try {
      const out = await api.reportEngineProof(connectionId, { report_id: reportId, record_id: effectiveRecord });
      showPdf(out.content_base64);
      setProofPages(out.pages);
      setPublishedPages(out.pages);
      setIsDraft(false);
    } catch (err) {
      toast.error(msg(err, "Odoo couldn't print this record."));
    } finally {
      setProofing(false);
    }
  }, [connectionId, reportId, effectiveRecord]);

  const key = JSON.stringify(placements);
  const dirty = key !== JSON.stringify(saved);
  const ready = placements.every((p) => p.blocks.every(blockReady));

  // Draft proof: Odoo prints the unpublished blocks 1.2 s after the last edit (or when the
  // language/company changes). A newer edit cancels the older request; the last good PDF stays.
  useEffect(() => {
    if (!reportId || !effectiveRecord || (!dirty && !variant)) {
      setIsDraft(false);
      setDraftNote(null);
      return;
    }
    if (!ready) return;
    const t = window.setTimeout(async () => {
      draftAbort.current?.abort();
      const ctl = new AbortController();
      draftAbort.current = ctl;
      setDrafting(true);
      try {
        const out = await api.layoutDraft(
          connectionId,
          { report_id: reportId, record_id: effectiveRecord, placements, lang: variant?.lang ?? null, company_id: variant?.companyId ?? null, published_pages: publishedPages },
          ctl.signal,
        );
        if (ctl.signal.aborted) return;
        showPdf(out.content_base64);
        setProofPages(out.pages);
        setChecks(out.checks);
        setIsDraft(true);
        setDraftNote(out.ok ? null : `Not shown on the page yet: ${out.missing.join(", ")}`);
      } catch (err) {
        if (ctl.signal.aborted) return;
        setDraftNote(`Couldn't update the draft. ${msg(err, "")}`.trim());
      } finally {
        if (draftAbort.current === ctl) {
          draftAbort.current = null;
          setDrafting(false);
        }
      }
    }, 1200);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, reportId, effectiveRecord, variant?.key, connectionId, ready]);

  useEffect(() => () => draftAbort.current?.abort(), []);

  const runCompare = useCallback(async () => {
    if (!reportId || !effectiveRecord) return;
    setComparing(true);
    try {
      const out = await api.layoutCompare(connectionId, { report_id: reportId, record_id: effectiveRecord, placements });
      setCompare({ out, before: pdfUrlFromB64(out.before_base64), after: pdfUrlFromB64(out.after_base64) });
      setChecks(out.checks);
    } catch (err) {
      toast.error(msg(err, "Couldn't compare."));
    } finally {
      setComparing(false);
    }
  }, [connectionId, reportId, effectiveRecord, placements]);

  const loadVisualCompare = useCallback(async (): Promise<VisualCompareOut | null> => {
    if (!reportId || !effectiveRecord) return null;
    try {
      return await api.layoutCompareVisual(connectionId, { report_id: reportId, record_id: effectiveRecord, placements });
    } catch (err) {
      toast.error(msg(err, "Couldn't make the page pictures."));
      return null;
    }
  }, [connectionId, reportId, effectiveRecord, placements]);

  const closeCompare = useCallback(() => {
    setCompare((c) => {
      if (c) {
        URL.revokeObjectURL(c.before);
        URL.revokeObjectURL(c.after);
      }
      return null;
    });
  }, []);

  const undoPublish = useCallback(
    async (out: LayoutPublishOut) => {
      if (!reportId || !effectiveRecord) return;
      try {
        if (out.previous_placements?.length) {
          await api.layoutPublish(connectionId, { report_id: reportId, record_id: effectiveRecord, placements: out.previous_placements });
        } else if (out.previous_arch == null) {
          await api.reportEngineRevert(connectionId, { layer_view_id: out.layer_view_id, mode: "deactivate" });
        } else {
          toast("Earlier changes were made before blocks could be saved. Restore them from History.");
          return;
        }
        setLastPublish(null);
        toast.success("Publish undone");
        await load();
        await showProof();
      } catch (err) {
        toast.error(msg(err, "Can't undo."));
      }
    },
    [connectionId, reportId, effectiveRecord, load, showProof],
  );

  const publish = useCallback(async () => {
    if (!reportId || !effectiveRecord || !blockCount(placements) || offline) return;
    setPublishing(true);
    try {
      const out = await api.layoutPublish(connectionId, { report_id: reportId, record_id: effectiveRecord, placements });
      setLastPublish(out);
      showPdf(out.content_base64);
      setProofPages(out.pages);
      setPublishedPages(out.pages);
      setChecks(out.checks);
      setIsDraft(false);
      setSaved(placements);
      setLayout((l) => (l ? { ...l, layer: { id: out.layer_view_id, active: true }, earlier_changes: false } : l));
      toast.success("Published. You can also undo this later in History.", { duration: 10000, action: { label: "Undo publish", onClick: () => void undoPublish(out) } });
    } catch (err) {
      toast.error(msg(err, "Can't publish."));
    } finally {
      setPublishing(false);
    }
  }, [connectionId, reportId, effectiveRecord, placements, undoPublish, offline]);

  /** Turn off every Ingenium change on this document (Odoo's own layout stays as it is). */
  const removeAll = useCallback(async () => {
    const layer = layout?.layer;
    if (!layer?.active) return;
    try {
      await api.reportEngineRevert(connectionId, { layer_view_id: layer.id, mode: "deactivate" });
      toast.success("Your changes are off this document. Odoo's layout is back.");
      await load();
      await showProof();
    } catch (err) {
      toast.error(msg(err, "Can't turn the changes off."));
    }
  }, [connectionId, layout, load, showProof]);

  const fields: FieldOpt[] = useMemo(
    () =>
      Object.entries(data?.fields ?? {})
        .filter(([n]) => !n.startsWith("__"))
        .map(([name, f]) => ({ name, label: f.string || name, type: f.type ?? "" }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [data],
  );

  const variantList: Variant[] = useMemo(() => {
    const v = variants;
    if (!v) return [];
    return [
      ...v.languages.map((l) => ({ key: `lang:${l.code}`, label: `${l.name}${l.note ? ` (${l.note})` : ""}`, lang: l.code, companyId: null, recordId: l.record_id })),
      ...v.currencies.map((c) => ({ key: `cur:${c.id}`, label: `In ${c.name}`, lang: null, companyId: null, recordId: c.record_id })),
      ...v.companies.map((c) => ({ key: `co:${c.id}`, label: `As ${c.name}`, lang: null, companyId: c.id, recordId: c.record_id })),
    ];
  }, [variants]);

  return {
    offline,
    model,
    setModel,
    reportId,
    setReportId,
    data,
    layout,
    loading,
    loadError,
    reload: load,
    recordId,
    setRecordId,
    slot,
    setSlot,
    placements,
    setPlacements,
    dirty,
    ready,
    fields,
    variantList,
    variant,
    setVariant,
    proofUrl,
    proofPages,
    proofing,
    showProof,
    checks,
    drafting,
    draftNote,
    isDraft,
    publish,
    publishing,
    lastPublish,
    undoPublish,
    removeAll,
    compare,
    comparing,
    runCompare,
    loadVisualCompare,
    closeCompare,
  };
}

export type ReportDesignerState = ReturnType<typeof useReportDesigner>;

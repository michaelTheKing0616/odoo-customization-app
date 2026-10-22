"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, type Connection, type FieldRow } from "@/lib/api";
import {
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";
import {
  defaultQwebViewBlocks,
  tryParseQwebViewBlocks,
  type QwebViewBlock,
} from "./qwebViewBlocks";
import { refuseUnsafeQwebViewSave } from "./qwebUnsafeGate";
import type { QwebViewsCreateFormValues } from "./QwebViewsCreateForm";
import type { QwebViewDetail } from "./QwebViewsEditor";
import type { QwebViewListRow } from "./QwebViewsListPanel";

const QWEB_CAVEAT =
  "General QWeb views are ir.ui.view type=qweb. Use an extension view; overwrite needs advanced confirm. Not a freeform unsafe editor — the shared PDF-05 gate refuses script / t-raw / t-out / XXE / invent t-call.";

export function useQwebViewsPage(connectionId: string) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [views, setViews] = useState<QwebViewListRow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<QwebViewDetail | null>(null);
  const [arch, setArch] = useState("");
  const [blocks, setBlocks] = useState<QwebViewBlock[]>([]);
  const [editorTab, setEditorTab] = useState<"visual" | "source">("visual");
  const [strategy, setStrategy] = useState<"inherit" | "overwrite">("inherit");
  const [inheritXpath, setInheritXpath] = useState("//div[hasclass('page')]");
  const [inheritPosition, setInheritPosition] = useState("inside");
  const [existingTCalls, setExistingTCalls] = useState<string[]>([]);
  const [fields, setFields] = useState<FieldRow[]>([]);
  const [fieldsLoading, setFieldsLoading] = useState(false);
  const [form, setForm] = useState<QwebViewsCreateFormValues>({
    name: "Custom document",
    key: "x_mod.document",
    model: "res.partner",
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listHydrated, setListHydrated] = useState(false);
  const [excludeReportBound, setExcludeReportBound] = useState(true);

  const refresh = useCallback(async () => {
    const rows = await api.listQwebViews(connectionId, {
      exclude_report_bound: excludeReportBound,
    });
    setViews(rows);
  }, [connectionId, excludeReportBound]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  useEffect(() => {
    setListHydrated(false);
    refresh()
      .catch((err: Error) => setError(err.message))
      .finally(() => setListHydrated(true));
  }, [refresh]);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      setArch("");
      setBlocks([]);
      setExistingTCalls([]);
      return;
    }
    let cancelled = false;
    setBusy(true);
    api
      .getQwebView(connectionId, selectedId)
      .then((row) => {
        if (cancelled) return;
        setDetail(row);
        setArch(row.arch || "");
        setExistingTCalls(row.existing_t_call_targets || []);
        if (row.blocks_parseable && row.blocks?.length) {
          setBlocks(row.blocks as QwebViewBlock[]);
          setEditorTab("visual");
        } else {
          const parsed = tryParseQwebViewBlocks(row.arch || "");
          if (parsed && parsed.length) {
            setBlocks(parsed);
            setEditorTab("visual");
          } else {
            setBlocks([]);
            setEditorTab("source");
          }
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, selectedId]);

  useEffect(() => {
    const model = detail?.model || form.model;
    if (!model) {
      setFields([]);
      return;
    }
    let cancelled = false;
    setFieldsLoading(true);
    api
      .listFields(connectionId, model)
      .then((rows) => {
        if (!cancelled) setFields(rows);
      })
      .catch(() => {
        if (!cancelled) setFields([]);
      })
      .finally(() => {
        if (!cancelled) setFieldsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, detail?.model, form.model]);

  const canMutate = mutationAllowed(connection);
  const mutateBlocked = mutationBlockedReason(connection);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const starter = defaultQwebViewBlocks(form.name);
      const gate = refuseUnsafeQwebViewSave({
        arch: undefined,
        blocks: starter,
      });
      if (gate) {
        setError(gate);
        return;
      }
      const created = await api.createQwebView(connectionId, {
        name: form.name,
        key: form.key,
        model: form.model || undefined,
        wrap_external_layout: true,
        blocks: starter,
      });
      setNotice(`Created QWeb view #${created.id} (${created.key})`);
      await refresh();
      setSelectedId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSave() {
    if (selectedId == null) return;
    setBusy(true);
    setError(null);
    try {
      const gate = refuseUnsafeQwebViewSave({
        arch,
        blocks: editorTab === "visual" ? blocks : null,
        allowExistingTCalls: existingTCalls,
        inheritXpath: strategy === "inherit" ? inheritXpath : null,
        inheritPosition: strategy === "inherit" ? inheritPosition : null,
      });
      if (gate) {
        setError(gate);
        return;
      }
      const body: Parameters<typeof api.saveQwebView>[2] = {
        strategy,
        existing_t_call_targets: existingTCalls,
        inherit_xpath: strategy === "inherit" ? inheritXpath : undefined,
        inherit_position: strategy === "inherit" ? inheritPosition : undefined,
      };
      if (editorTab === "visual" && strategy === "inherit") {
        body.blocks = blocks;
      } else {
        body.arch = arch;
      }
      if (strategy === "overwrite") {
        const ok =
          typeof window !== "undefined" &&
          window.confirm(
            "Overwrite mutates this QWeb view arch directly (not an extension view). Use an extension view. Continue only if you understand the risks.",
          );
        if (!ok) {
          setNotice("Overwrite cancelled — switch to Inherit or confirm to proceed.");
          return;
        }
        body.confirm_advanced = true;
        body.confirm_phrase = "I understand the risks";
      }
      const saved = await api.saveQwebView(connectionId, selectedId, body);
      setNotice(
        strategy === "inherit"
          ? `Saved inherit child #${saved.id} (${saved.arch_len} chars)`
          : `Overwrote view #${saved.id} (${saved.arch_len} chars)`,
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return {
    connection,
    qwebCaveat: QWEB_CAVEAT,
    views,
    selectedId,
    setSelectedId,
    detail,
    arch,
    setArch,
    blocks,
    setBlocks,
    editorTab,
    setEditorTab,
    strategy,
    setStrategy,
    inheritXpath,
    setInheritXpath,
    inheritPosition,
    setInheritPosition,
    existingTCalls,
    fields,
    fieldsLoading,
    form,
    setForm,
    error,
    setError,
    notice,
    busy,
    listHydrated,
    canMutate,
    mutateBlocked,
    excludeReportBound,
    setExcludeReportBound,
    onCreate,
    onSave,
    formatError: (msg: string) => msg,
  };
}

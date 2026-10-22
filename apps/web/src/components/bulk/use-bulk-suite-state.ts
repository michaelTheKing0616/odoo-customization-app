"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  type BulkRunOut,
  type BulkTransitionButton,
  type Connection,
  type DedupeScanOut,
  type ModelRow,
  type SecurityPreviewOut,
} from "@/lib/api";
import { newProgressRunId } from "@/lib/progress/run-id";
import type { BulkConfirmMode } from "./bulk-helpers";

export function useBulkSuiteState(connectionId: string) {
  const searchParams = useSearchParams();
  const showRecipes = searchParams.get("recipes") === "1";

  const [connection, setConnection] = useState<Connection | null>(null);
  const [models, setModels] = useState<ModelRow[]>([]);
  const [model, setModel] = useState("x_lib_book");
  const [modelQuery, setModelQuery] = useState("");
  const [buttons, setButtons] = useState<BulkTransitionButton[]>([]);
  const [method, setMethod] = useState("");
  const [selectionMode, setSelectionMode] = useState<"domain" | "ids">("domain");
  const [domainText, setDomainText] = useState("[]");
  const [idsText, setIdsText] = useState("");
  const [busy, setBusy] = useState(false);
  const [progressRunId, setProgressRunId] = useState<string | null>(null);
  const [discoverBusy, setDiscoverBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<BulkRunOut | null>(null);
  const [runControlBusy, setRunControlBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmMode, setConfirmMode] = useState<BulkConfirmMode>("transition");
  const [valuesText, setValuesText] = useState('{"x_name": "Updated via bulk suite"}');
  const [matchFieldsText, setMatchFieldsText] = useState("x_name");
  const [dedupeMode, setDedupeMode] = useState<"exact" | "fuzzy">("exact");
  const [scanResult, setScanResult] = useState<DedupeScanOut | null>(null);
  const [selectedGroupIdx, setSelectedGroupIdx] = useState(0);
  const [winnerId, setWinnerId] = useState<number | null>(null);
  const [activityTypes, setActivityTypes] = useState<Array<{ id: number; name: string }>>([]);
  const [activityTypeId, setActivityTypeId] = useState("");
  const [activitySummary, setActivitySummary] = useState("Follow up");
  const [activityDeadline, setActivityDeadline] = useState("");
  const [activityProbe, setActivityProbe] = useState<string | null>(null);
  const [securityUserIds, setSecurityUserIds] = useState("");
  const [securityGroupIds, setSecurityGroupIds] = useState("");
  const [securityMode, setSecurityMode] = useState<"add" | "remove" | "offboard">("add");
  const [securityPreview, setSecurityPreview] = useState<SecurityPreviewOut | null>(null);
  const [securityOffboardDeactivate, setSecurityOffboardDeactivate] = useState(false);
  const [portalPartnerIds, setPortalPartnerIds] = useState("");
  const [portalAction, setPortalAction] = useState<"grant" | "revoke">("grant");
  const [sendBody, setSendBody] = useState("<p>Bulk message</p>");
  const [sendSubject, setSendSubject] = useState("Bulk update");
  const [sendTemplateId, setSendTemplateId] = useState("");
  const [pageHydrated, setPageHydrated] = useState(false);

  const filteredModels = useMemo(() => {
    const q = modelQuery.trim().toLowerCase();
    if (!q) return models.slice(0, 200);
    return models
      .filter(
        (m) =>
          m.model.toLowerCase().includes(q) ||
          (m.name && m.name.toLowerCase().includes(q)),
      )
      .slice(0, 200);
  }, [models, modelQuery]);

  const selectedButton = buttons.find((b) => b.name === method);
  const selectedGroup = scanResult?.groups[selectedGroupIdx] ?? null;
  const loserIds =
    selectedGroup && winnerId != null
      ? selectedGroup.records.map((r) => r.id).filter((id) => id !== winnerId)
      : [];

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setPageHydrated(false);
      try {
        const [conn, mods] = await Promise.all([
          api.getConnection(connectionId),
          api.listModels(connectionId),
        ]);
        if (cancelled) return;
        setConnection(conn);
        setModels(mods);
        if (mods.some((m) => m.model === "x_lib_book")) {
          setModel("x_lib_book");
        } else if (mods[0]) {
          setModel(mods[0].model);
        }
        try {
          const types = await api.listActivityTypes(connectionId);
          if (!cancelled) {
            setActivityTypes(types.map((t) => ({ id: t.id, name: t.name })));
            if (types[0]) setActivityTypeId(String(types[0].id));
          }
        } catch {
          /* mail may be unavailable */
        }
        try {
          const types = await api.listActivityTypes(connectionId);
          if (!cancelled) {
            setActivityTypes(types.map((t) => ({ id: t.id, name: t.name })));
            if (types[0]) setActivityTypeId(String(types[0].id));
          }
        } catch {
          /* mail may be unavailable */
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load connection");
        }
      } finally {
        if (!cancelled) setPageHydrated(true);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  function beginProgressRun(prefix = "bulk") {
    const id = newProgressRunId(prefix);
    setProgressRunId(id);
    return id;
  }

  function clearProgressRunId() {
    setProgressRunId(null);
  }

  return {
    connectionId,
    showRecipes,
    connection,
    models,
    model,
    setModel,
    modelQuery,
    setModelQuery,
    buttons,
    setButtons,
    method,
    setMethod,
    selectionMode,
    setSelectionMode,
    domainText,
    setDomainText,
    idsText,
    setIdsText,
    busy,
    setBusy,
    progressRunId,
    beginProgressRun,
    clearProgressRunId,
    discoverBusy,
    setDiscoverBusy,
    error,
    setError,
    notice,
    setNotice,
    result,
    setResult,
    runControlBusy,
    setRunControlBusy,
    confirmOpen,
    setConfirmOpen,
    confirmMode,
    setConfirmMode,
    valuesText,
    setValuesText,
    matchFieldsText,
    setMatchFieldsText,
    dedupeMode,
    setDedupeMode,
    scanResult,
    setScanResult,
    selectedGroupIdx,
    setSelectedGroupIdx,
    winnerId,
    setWinnerId,
    activityTypes,
    activityTypeId,
    setActivityTypeId,
    activitySummary,
    setActivitySummary,
    activityDeadline,
    setActivityDeadline,
    activityProbe,
    setActivityProbe,
    securityUserIds,
    setSecurityUserIds,
    securityGroupIds,
    setSecurityGroupIds,
    securityMode,
    setSecurityMode,
    securityPreview,
    setSecurityPreview,
    securityOffboardDeactivate,
    setSecurityOffboardDeactivate,
    portalPartnerIds,
    setPortalPartnerIds,
    portalAction,
    setPortalAction,
    sendBody,
    setSendBody,
    sendSubject,
    setSendSubject,
    sendTemplateId,
    setSendTemplateId,
    pageHydrated,
    filteredModels,
    selectedButton,
    selectedGroup,
    loserIds,
  };
}

export type BulkSuiteState = ReturnType<typeof useBulkSuiteState>;

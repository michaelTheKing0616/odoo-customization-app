"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  BulkRunOut,
  BulkTransitionButton,
  ConfirmationRequiredError,
  Connection,
  DedupeScanOut,
  ModelRow,
  SecurityPreviewOut,
} from "@/lib/api";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { BulkResultTable, type BulkRunResult } from "@/components/ui/BulkResultTable";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Card, EmptyState, PageHeader } from "@/components/ui/layout-primitives";
import { EMPTY_STATES } from "@/lib/copy-guide";
import { ScanToFieldPanel } from "@/components/scanner/ScanToFieldPanel";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";

const CONFIRM_PHRASE = "I understand the risks";

function bulkRunToTable(result: BulkRunOut): BulkRunResult {
  return {
    run_id: result.run_id,
    operation: result.operation,
    model: result.model,
    total: result.total,
    succeeded: result.succeeded,
    failed: result.failed,
    per_record: result.per_record.map((r) => ({
      record_id: r.id,
      display_name: r.display_name,
      ok: r.ok,
      error: r.error,
    })),
    dry_run: result.dry_run,
    message: result.message,
    status: result.status,
    pending_ids: result.pending_ids,
    processed_count: result.processed_count,
    aborted: result.aborted,
    can_continue: result.can_continue,
  };
}

export default function BulkSuitePage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

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
  const [discoverBusy, setDiscoverBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<BulkRunOut | null>(null);
  const [runControlBusy, setRunControlBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmMode, setConfirmMode] = useState<
    | "transition"
    | "mass_edit"
    | "dedupe_merge"
    | "activities"
    | "security"
    | "portal"
    | "send_message"
  >("transition");
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
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  async function discover() {
    setDiscoverBusy(true);
    setError(null);
    setButtons([]);
    setMethod("");
    try {
      const res = await api.bulkTransitions(connectionId, model.trim());
      setButtons(res.buttons);
      const firstSafe = res.buttons.find((b) => b.bulk_safe);
      if (firstSafe) setMethod(firstSafe.name);
      else if (res.buttons[0]) setMethod(res.buttons[0].name);
      setNotice(
        res.buttons.length
          ? `Discovered ${res.buttons.length} object button(s) on form view.`
          : "No object buttons found on the primary form view.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Discovery failed");
    } finally {
      setDiscoverBusy(false);
    }
  }

  function parseSelection(): { domain?: unknown[]; ids?: number[] } {
    if (selectionMode === "domain") {
      try {
        const domain = JSON.parse(domainText) as unknown[];
        if (!Array.isArray(domain)) throw new Error("domain must be a list");
        return { domain };
      } catch {
        throw new Error("Invalid domain JSON — use Odoo domain list, e.g. []");
      }
    }
    const ids = idsText
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => Number(s))
      .filter((n) => Number.isFinite(n) && n > 0);
    if (!ids.length) throw new Error("Enter at least one numeric record id");
    return { ids };
  }

  async function continueSampleRun() {
    if (!result?.run_id) return;
    setRunControlBusy(true);
    setError(null);
    try {
      const res = await api.bulkRunContinue(connectionId, result.run_id);
      setResult(res);
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Continue failed");
    } finally {
      setRunControlBusy(false);
    }
  }

  async function abortSampleRun() {
    if (!result?.run_id) return;
    setRunControlBusy(true);
    setError(null);
    try {
      const res = await api.bulkRunAbort(connectionId, result.run_id);
      setResult(res);
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Abort failed");
    } finally {
      setRunControlBusy(false);
    }
  }


  async function run(dryRun: boolean, phrase?: string) {
    if (!method.trim()) {
      setError("Pick a discovered transition method.");
      return;
    }
    if (!dryRun && selectedButton && !selectedButton.bulk_safe) {
      setError(`Method is not bulk-safe: ${selectedButton.reason}`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const selection = parseSelection();
      const res = await api.bulkTransitionRun(connectionId, {
        model: model.trim(),
        method: method.trim(),
        ...selection,
        dry_run: dryRun,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("transition");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Run failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function runMassEdit(dryRun: boolean, phrase?: string) {
    setBusy(true);
    setError(null);
    try {
      let values: Record<string, unknown>;
      try {
        values = JSON.parse(valuesText) as Record<string, unknown>;
        if (!values || typeof values !== "object" || Array.isArray(values)) {
          throw new Error("values must be a JSON object");
        }
      } catch {
        throw new Error('Invalid values JSON — e.g. {"x_name": "New title"}');
      }
      const selection = parseSelection();
      const res = await api.bulkMassEdit(connectionId, {
        model: model.trim(),
        values,
        ...selection,
        dry_run: dryRun,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("mass_edit");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Mass edit failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function scanDedupe() {
    setBusy(true);
    setError(null);
    setScanResult(null);
    try {
      const match_fields = matchFieldsText
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      if (!match_fields.length) throw new Error("Enter at least one match field");
      const res = await api.bulkDedupeScan(connectionId, {
        model: model.trim(),
        match_fields,
        mode: dedupeMode,
      });
      setScanResult(res);
      setSelectedGroupIdx(0);
      if (res.groups[0]?.records[0]) {
        setWinnerId(res.groups[0].records[0].id);
      }
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function mergeDedupe(dryRun: boolean, phrase?: string) {
    if (winnerId == null || !loserIds.length) {
      setError("Scan duplicate groups and pick a winner first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkDedupeMerge(connectionId, {
        model: model.trim(),
        winner_id: winnerId,
        loser_ids: loserIds,
        dry_run: dryRun,
        archive_or_delete: "archive",
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("dedupe_merge");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Merge failed");
      }
    } finally {
      setBusy(false);
    }
  }

  function parseIdList(text: string, label: string): number[] {
    const ids = text
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => Number(s))
      .filter((n) => Number.isFinite(n) && n > 0);
    if (!ids.length) throw new Error(`Enter at least one ${label} id`);
    return ids;
  }

  async function probeActivities() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkActivitiesProbe(connectionId, model.trim());
      setActivityProbe(res.message);
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Activity probe failed");
    } finally {
      setBusy(false);
    }
  }

  async function runActivities(dryRun: boolean, phrase?: string) {
    if (!activityTypeId) {
      setError("Pick an activity type.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const selection = parseSelection();
      const res = await api.bulkActivities(connectionId, {
        model: model.trim(),
        ...selection,
        activity_type_id: Number(activityTypeId),
        summary: activitySummary,
        date_deadline: activityDeadline || new Date().toISOString().slice(0, 10),
        dry_run: dryRun,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("activities");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Bulk activities failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function previewSecurity() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkSecurityPreview(connectionId, {
        user_ids: parseIdList(securityUserIds, "user"),
        group_ids: securityMode === "offboard" ? [] : parseIdList(securityGroupIds, "group"),
        mode: securityMode,
        deactivate: securityOffboardDeactivate,
      });
      setSecurityPreview(res);
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Security preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function applySecurity(dryRun: boolean, phrase?: string) {
    if (!dryRun && !securityPreview) {
      setError("Run security preview before apply.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkSecurityApply(connectionId, {
        user_ids: parseIdList(securityUserIds, "user"),
        group_ids: securityMode === "offboard" ? [] : parseIdList(securityGroupIds, "group"),
        mode: securityMode,
        deactivate: securityOffboardDeactivate,
        dry_run: dryRun,
        preview_acknowledged: dryRun || Boolean(securityPreview),
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("security");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Security apply failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function runPortal(dryRun: boolean, phrase?: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkPortal(connectionId, {
        partner_ids: parseIdList(portalPartnerIds, "partner"),
        action: portalAction,
        dry_run: dryRun,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("portal");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Portal batch failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function runSendMessage(dryRun: boolean, phrase?: string) {
    if (!model.trim()) {
      setError("Select a model first.");
      return;
    }
    if (!sendBody.trim() && !sendTemplateId.trim()) {
      setError("Enter message body or a mail template id.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const selection = parseSelection();
      const res = await api.bulkSendMessage(connectionId, {
        model,
        ...selection,
        body: sendBody.trim() || null,
        subject: sendSubject.trim() || null,
        mail_template_id: sendTemplateId.trim() ? Number(sendTemplateId) : null,
        dry_run: dryRun,
        ...(dryRun ? {} : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("send_message");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Send message failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl" data-testid="bulk-suite-page">
      <PageHeader
        title="Bulk Suite"
        description="Discover form-view workflow buttons per model and run them in bulk with dry-run first. Runs as the connected Odoo user — partial failures are reported per record."
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      {connection ? <FirstWriteInterstitial connection={connection} /> : null}

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      {!result && !busy ? (
        <div className="mt-6">
        <EmptyState
          title="Bulk operations"
          description={EMPTY_STATES.bulkSuite}
        />
        </div>
      ) : null}

        <Card className="mt-6 space-y-4 p-4">
          <label className="block text-sm">
            Model
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              list="bulk-suite-models"
            />
            <datalist id="bulk-suite-models">
              {filteredModels.map((m) => (
                <option key={m.model} value={m.model}>
                  {m.name}
                </option>
              ))}
            </datalist>
          </label>
          <label className="block text-sm">
            Filter models
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 text-sm"
              value={modelQuery}
              onChange={(e) => setModelQuery(e.target.value)}
              placeholder="Search technical or label name"
            />
          </label>
          <button
            type="button"
            className="odoo-btn-secondary"
            disabled={discoverBusy || !model.trim()}
            onClick={() => void discover()}
          >
            {discoverBusy ? "Discovering…" : "Discover transitions"}
          </button>

          {buttons.length > 0 && (
            <label className="block text-sm">
              Transition method
              <select
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={method}
                onChange={(e) => setMethod(e.target.value)}
              >
                {buttons.map((b) => (
                  <option key={b.name} value={b.name}>
                    {b.bulk_safe ? "" : "⚠ "}
                    {b.label} ({b.name})
                  </option>
                ))}
              </select>
            </label>
          )}
          {selectedButton && (
            <p
              className={`text-sm ${selectedButton.bulk_safe ? "text-[var(--odoo-muted)]" : "text-[var(--odoo-danger)]"}`}
            >
              {selectedButton.bulk_safe ? "Bulk-safe" : "Not bulk-safe"} — {selectedButton.reason}
            </p>
          )}

          <fieldset className="space-y-2 text-sm">
            <legend className="font-medium">Record selection</legend>
            <label className="mr-4 inline-flex items-center gap-2">
              <input
                type="radio"
                checked={selectionMode === "domain"}
                onChange={() => setSelectionMode("domain")}
              />
              Domain
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="radio"
                checked={selectionMode === "ids"}
                onChange={() => setSelectionMode("ids")}
              />
              Explicit ids
            </label>
          </fieldset>

          {selectionMode === "domain" ? (
            <label className="block text-sm">
              Domain (JSON list, cap 1000)
              <textarea
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-xs"
                rows={3}
                value={domainText}
                onChange={(e) => setDomainText(e.target.value)}
              />
            </label>
          ) : (
            <label className="block text-sm">
              Record ids (comma or space separated)
              <input
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
                value={idsText}
                onChange={(e) => setIdsText(e.target.value)}
              />
            </label>
          )}

          <div className="flex flex-wrap gap-2 pt-2">
            <button
              type="button"
              className="odoo-btn-secondary"
              disabled={busy || !method}
              onClick={() => void run(true)}
            >
              Dry run
            </button>
            <button
              type="button"
              className="odoo-btn-primary"
              disabled={busy || !method || (selectedButton ? !selectedButton.bulk_safe : false)}
              onClick={() => void run(false)}
            >
              Execute
            </button>
          </div>
        </Card>

        <Card className="mt-6 space-y-4 p-4">
          <h2 className="text-lg font-semibold">Mass field edit</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            One write per batch — validates field types and protected-module policy before apply.
          </p>
          <label className="block text-sm">
            Values (JSON object)
            <textarea
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-xs"
              rows={3}
              value={valuesText}
              onChange={(e) => setValuesText(e.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="odoo-btn-secondary"
              disabled={busy}
              onClick={() => void runMassEdit(true)}
            >
              Dry run preview
            </button>
            <button
              type="button"
              className="odoo-btn-primary"
              disabled={busy}
              onClick={() => void runMassEdit(false)}
            >
              Apply mass edit
            </button>
          </div>
        </Card>

        <Card className="mt-6 space-y-4 p-4">
          <h2 className="text-lg font-semibold">Duplicate detection & merge</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Scan by field(s), pick a winner per group, relink inbound FKs, then archive losers.
          </p>
          {scanResult?.partner_merge_available && (
            <p className="text-sm text-[var(--odoo-warning)]">
              Odoo partner merge wizard is available — prefer it for res.partner on this instance.
            </p>
          )}
          <label className="block text-sm">
            Match fields (comma separated)
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={matchFieldsText}
              onChange={(e) => setMatchFieldsText(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Mode
            <select
              className="mt-1 border border-[var(--odoo-border)] bg-white px-2 py-1.5"
              value={dedupeMode}
              onChange={(e) => setDedupeMode(e.target.value as "exact" | "fuzzy")}
            >
              <option value="exact">Exact</option>
              <option value="fuzzy">Fuzzy (normalized / single-field clustering)</option>
            </select>
          </label>
          <button
            type="button"
            className="odoo-btn-secondary"
            disabled={busy}
            onClick={() => void scanDedupe()}
          >
            Scan duplicates
          </button>
          {scanResult && scanResult.groups.length > 0 && (
            <div className="space-y-3 text-sm">
              <label className="block">
                Duplicate group
                <select
                  className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                  value={selectedGroupIdx}
                  onChange={(e) => {
                    const idx = Number(e.target.value);
                    setSelectedGroupIdx(idx);
                    const g = scanResult.groups[idx];
                    if (g?.records[0]) setWinnerId(g.records[0].id);
                  }}
                >
                  {scanResult.groups.map((g, idx) => (
                    <option key={g.group_key} value={idx}>
                      {g.group_key} ({g.records.length} records)
                    </option>
                  ))}
                </select>
              </label>
              {selectedGroup && (
                <fieldset className="space-y-2">
                  <legend>Winner record</legend>
                  {selectedGroup.records.map((rec) => (
                    <label key={rec.id} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="dedupe-winner"
                        checked={winnerId === rec.id}
                        onChange={() => setWinnerId(rec.id)}
                      />
                      <span>
                        {rec.display_name} (#{rec.id}) —{" "}
                        {JSON.stringify(rec.preview)}
                      </span>
                    </label>
                  ))}
                </fieldset>
              )}
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="odoo-btn-secondary"
                  disabled={busy || winnerId == null}
                  onClick={() => void mergeDedupe(true)}
                >
                  Dry run merge
                </button>
                <button
                  type="button"
                  className="odoo-btn-primary"
                  disabled={busy || winnerId == null}
                  onClick={() => void mergeDedupe(false)}
                >
                  Merge group
                </button>
              </div>
            </div>
          )}
        </Card>

        <Card className="mt-6 space-y-4 p-4">
          <h2 className="text-lg font-semibold">Bulk activities</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Schedule mail.activity rows on the selected model records (requires mail.activity.mixin).
          </p>
          {activityProbe && (
            <p className="text-xs text-[var(--odoo-muted)]">{activityProbe}</p>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            <label className="block text-sm">
              Activity type
              <select
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={activityTypeId}
                onChange={(e) => setActivityTypeId(e.target.value)}
              >
                {activityTypes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              Deadline (YYYY-MM-DD)
              <input
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={activityDeadline}
                onChange={(e) => setActivityDeadline(e.target.value)}
                placeholder="2026-08-10"
              />
            </label>
            <label className="block text-sm md:col-span-2">
              Summary
              <input
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={activitySummary}
                onChange={(e) => setActivitySummary(e.target.value)}
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void probeActivities()}>
              Probe model
            </button>
            <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void runActivities(true)}>
              Dry run
            </button>
            <button type="button" className="odoo-btn-primary" disabled={busy} onClick={() => void runActivities(false)}>
              Schedule
            </button>
          </div>
        </Card>

        <Card className="mt-6 space-y-4 p-4">
          <h2 className="text-lg font-semibold">Bulk security</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Preview group membership changes first — implied groups are warned, never edited.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="block text-sm">
              User ids
              <input
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
                value={securityUserIds}
                onChange={(e) => setSecurityUserIds(e.target.value)}
                placeholder="2, 5"
              />
            </label>
            <label className="block text-sm">
              Mode
              <select
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={securityMode}
                onChange={(e) =>
                  setSecurityMode(e.target.value as "add" | "remove" | "offboard")
                }
              >
                <option value="add">Add to groups</option>
                <option value="remove">Remove from groups</option>
                <option value="offboard">Offboard (strip non-base groups)</option>
              </select>
            </label>
            {securityMode !== "offboard" && (
              <label className="block text-sm md:col-span-2">
                Group ids
                <input
                  className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
                  value={securityGroupIds}
                  onChange={(e) => setSecurityGroupIds(e.target.value)}
                  placeholder="8, 12"
                />
              </label>
            )}
            {securityMode === "offboard" && (
              <label className="flex items-center gap-2 text-sm md:col-span-2">
                <input
                  type="checkbox"
                  checked={securityOffboardDeactivate}
                  onChange={(e) => setSecurityOffboardDeactivate(e.target.checked)}
                />
                Also deactivate users
              </label>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void previewSecurity()}>
              Preview diff
            </button>
            <button type="button" className="odoo-btn-secondary" disabled={busy || !securityPreview} onClick={() => void applySecurity(true)}>
              Dry run apply
            </button>
            <button type="button" className="odoo-btn-primary" disabled={busy || !securityPreview} onClick={() => void applySecurity(false)}>
              Apply
            </button>
          </div>
          {securityPreview && (
            <div className="rounded border border-[var(--odoo-border)] p-3 text-sm">
              <p className="font-medium">{securityPreview.message}</p>
              {securityPreview.users.map((u) => (
                <div key={u.user_id} className="mt-2 border-t border-[var(--odoo-border)]/60 pt-2">
                  <div>{u.user_name} (#{u.user_id})</div>
                  {u.add_groups.length > 0 && (
                    <div className="text-xs text-[var(--odoo-muted)]">
                      Add: {u.add_groups.map((g) => g.name).join(", ")}
                    </div>
                  )}
                  {u.remove_groups.length > 0 && (
                    <div className="text-xs text-[var(--odoo-muted)]">
                      Remove: {u.remove_groups.map((g) => g.name).join(", ")}
                    </div>
                  )}
                  {u.implied_warnings.map((w) => (
                    <div key={w} className="text-xs text-amber-800">
                      {w}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="mt-6 space-y-4 p-4">
          <h2 className="text-lg font-semibold">Bulk portal access</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Grant or revoke portal access for partners — missing email fails per partner, not the batch.
          </p>
          <label className="block text-sm">
            Partner ids
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={portalPartnerIds}
              onChange={(e) => setPortalPartnerIds(e.target.value)}
              placeholder="14, 18"
            />
          </label>
          <label className="block text-sm">
            Action
            <select
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
              value={portalAction}
              onChange={(e) => setPortalAction(e.target.value as "grant" | "revoke")}
            >
              <option value="grant">Grant portal</option>
              <option value="revoke">Revoke portal</option>
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void runPortal(true)}>
              Dry run
            </button>
            <button type="button" className="odoo-btn-primary" disabled={busy} onClick={() => void runPortal(false)}>
              Execute
            </button>
          </div>
        </Card>

        <Card className="mt-6 space-y-4 p-4">
          <h2 className="text-lg font-semibold">Bulk send message</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Post one threaded message per record via message_post — not Odoo mass-mail composer.
            Target records with ids or domain above.
          </p>
          <label className="block text-sm">
            Subject
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
              value={sendSubject}
              onChange={(e) => setSendSubject(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Body (HTML)
            <textarea
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              rows={3}
              value={sendBody}
              onChange={(e) => setSendBody(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Mail template id (optional)
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={sendTemplateId}
              onChange={(e) => setSendTemplateId(e.target.value)}
              placeholder="12"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void runSendMessage(true)}>
              Dry run
            </button>
            <button type="button" className="odoo-btn-primary" disabled={busy} onClick={() => void runSendMessage(false)}>
              Send
            </button>
          </div>
        </Card>

        {result ? (
          <Card className="mt-6 overflow-x-auto p-4">
            <h2 className="text-lg font-semibold text-ink">Results</h2>
            {result.preview && result.preview.length > 0 ? (
              <table className="mt-3 w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="py-1 pr-2">Id</th>
                    <th className="py-1 pr-2">Record</th>
                    <th className="py-1 pr-2">Before</th>
                    <th className="py-1">After</th>
                  </tr>
                </thead>
                <tbody>
                  {result.preview.map((row) => (
                    <tr key={row.id} className="border-b border-border-subtle/50">
                      <td className="py-1 pr-2 font-mono">{row.id}</td>
                      <td className="py-1 pr-2">{row.display_name}</td>
                      <td className="py-1 pr-2 font-mono text-xs">
                        {JSON.stringify(row.before)}
                      </td>
                      <td className="py-1 font-mono text-xs">{JSON.stringify(row.after)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
            {result.relinks && result.relinks.length > 0 ? (
              <table className="mt-3 w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="py-1 pr-2">Model</th>
                    <th className="py-1 pr-2">Field</th>
                    <th className="py-1 pr-2">Type</th>
                    <th className="py-1">Rows relinked</th>
                  </tr>
                </thead>
                <tbody>
                  {result.relinks.map((row) => (
                    <tr
                      key={`${row.model}.${row.field}`}
                      className="border-b border-border-subtle/50"
                    >
                      <td className="py-1 pr-2 font-mono">{row.model}</td>
                      <td className="py-1 pr-2 font-mono">{row.field}</td>
                      <td className="py-1 pr-2">{row.ttype}</td>
                      <td className="py-1">{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
            <div className="mt-4">
              <BulkResultTable
                result={bulkRunToTable(result)}
                onContinue={result.can_continue ? continueSampleRun : undefined}
                onAbort={result.status === "sample_paused" ? abortSampleRun : undefined}
                continueBusy={runControlBusy}
                abortBusy={runControlBusy}
              />
              {result.snapshot_id && result.operation === "dedupe_merge" && !result.dry_run ? (
                <p className="mt-3 text-sm">
                  <a
                    className="text-accent underline"
                    href={`/api/connections/${connectionId}/snapshots/${result.snapshot_id}/artifact.json`}
                    data-testid="dedupe-merge-backup-download"
                  >
                    Download merge backup (JSON)
                  </a>
                </p>
              ) : null}
            </div>
          </Card>
        ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
        phrase={CONFIRM_PHRASE}
        title={
          confirmMode === "mass_edit"
            ? "Confirm mass field edit"
            : confirmMode === "dedupe_merge"
              ? "Confirm duplicate merge"
              : confirmMode === "activities"
                ? "Confirm bulk activities"
                : confirmMode === "security"
                  ? "Confirm security apply"
                  : confirmMode === "portal"
                    ? "Confirm portal batch"
                    : confirmMode === "send_message"
                      ? "Confirm bulk send message"
                      : "Confirm bulk transition"
        }
        warning={
          confirmMode === "mass_edit"
            ? `This will write field values on live ${model} records. Dry-run first when unsure.`
            : confirmMode === "dedupe_merge"
              ? `Merge ${loserIds.length} duplicate(s) into winner #${winnerId ?? "?"} on ${model}.`
              : confirmMode === "activities"
                ? `Schedule activities on live ${model} records.`
                : confirmMode === "security"
                  ? `Apply security changes (${securityMode}) on selected users.`
                  : confirmMode === "portal"
                    ? `Portal ${portalAction} on selected partners.`
                    : confirmMode === "send_message"
                      ? `Post threaded messages on live ${model} records.`
                      : selectedButton
                      ? `This will call ${method} on live ${model} records. Dry-run first when unsure.`
                      : "Bulk workflow transition on live ERP data."
        }
        risks={
          confirmMode === "mass_edit"
            ? [
                "Batch write on live ERP records",
                "Protected-module policy blocks tier-1 and non-x_* fields on tier-2",
              ]
            : confirmMode === "dedupe_merge"
              ? [
                  "Partially reversible — snapshot stored but manual recovery may be needed",
                  "Inbound FK rows and chatter are rewritten; losers archived by default",
                ]
              : confirmMode === "activities"
                ? [
                    "Creates mail.activity rows and may notify assignees",
                    "Requires mail.activity.mixin on the target model",
                  ]
              : confirmMode === "security"
                ? [
                    "Changes res.users group membership immediately",
                    "Adding groups may imply additional groups (not edited directly)",
                  ]
                : confirmMode === "portal"
                  ? [
                      "Grant may create portal users and send access emails",
                      "Partners without email are skipped individually on grant",
                    ]
                  : confirmMode === "send_message"
                    ? [
                        "One message_post per record — not mass-mail composer",
                        "Template renders per record when mail_template_id is set",
                      ]
                    : [
                      "Runs as the connected Odoo user — side effects may include mail, stock, or accounting",
                      "Successful rows are not auto-undone if some records fail",
                    ]
        }
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) =>
          void (confirmMode === "mass_edit"
            ? runMassEdit(false, phrase)
            : confirmMode === "dedupe_merge"
              ? mergeDedupe(false, phrase)
              : confirmMode === "activities"
                ? runActivities(false, phrase)
                : confirmMode === "security"
                  ? applySecurity(false, phrase)
                  : confirmMode === "portal"
                    ? runPortal(false, phrase)
                    : confirmMode === "send_message"
                      ? runSendMessage(false, phrase)
                      : run(false, phrase))
        }
      />
      <ScanToFieldPanel connectionId={connectionId} connection={connection} defaultModel={model} />
    </div>
  );
}

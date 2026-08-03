"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  BulkRunOut,
  BulkTransitionButton,
  ConfirmationRequiredError,
  Connection,
  CronRowOut,
  ModelRow,
} from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";

const CONFIRM_PHRASE = "I understand the risks";

type ConfirmMode = "run_now" | "create" | "deactivate";

export default function CronManagerPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [crons, setCrons] = useState<CronRowOut[]>([]);
  const [probe, setProbe] = useState<Record<string, unknown> | null>(null);
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "inactive">("all");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<BulkRunOut | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmMode, setConfirmMode] = useState<ConfirmMode>("run_now");
  const [deactivateTarget, setDeactivateTarget] = useState<CronRowOut | null>(null);

  const [models, setModels] = useState<ModelRow[]>([]);
  const [model, setModel] = useState("x_blk_wf_item");
  const [method, setMethod] = useState("");
  const [buttons, setButtons] = useState<BulkTransitionButton[]>([]);
  const [cronName, setCronName] = useState("Nightly maintenance");
  const [intervalNumber, setIntervalNumber] = useState(1);
  const [intervalType, setIntervalType] = useState<
    "minutes" | "hours" | "days" | "weeks" | "months"
  >("days");

  const filteredCrons = useMemo(() => {
    const q = query.trim().toLowerCase();
    return crons.filter((c) => {
      if (activeFilter === "active" && !c.active) return false;
      if (activeFilter === "inactive" && c.active) return false;
      if (!q) return true;
      return (
        c.name.toLowerCase().includes(q) ||
        (c.model_name && c.model_name.toLowerCase().includes(q)) ||
        c.description.toLowerCase().includes(q)
      );
    });
  }, [crons, query, activeFilter]);

  const refreshCrons = useCallback(async () => {
    const res = await api.bulkCrons(connectionId, { limit: 300 });
    setCrons(res.crons);
    setProbe(res.probe);
  }, [connectionId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [conn, mods] = await Promise.all([
          api.getConnection(connectionId),
          api.listModels(connectionId),
          refreshCrons(),
        ]);
        if (cancelled) return;
        setConnection(conn);
        setModels(mods);
        if (mods.some((m) => m.model === "x_blk_wf_item")) {
          setModel("x_blk_wf_item");
        } else if (mods[0]) {
          setModel(mods[0].model);
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
  }, [connectionId, refreshCrons]);

  async function discoverMethods() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkTransitions(connectionId, model.trim());
      setButtons(res.buttons.filter((b) => b.bulk_safe));
      if (res.buttons[0]) {
        setMethod(res.buttons[0].name);
      }
      setNotice(`Found ${res.buttons.length} object button(s) on ${res.model}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Discovery failed");
    } finally {
      setBusy(false);
    }
  }

  function toggleSelected(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function runNow(dryRun: boolean, phrase?: string) {
    const ids = [...selected];
    if (!ids.length) {
      setError("Select at least one scheduled action.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkCronRunNow(connectionId, {
        cron_ids: ids,
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
        setConfirmMode("run_now");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Run-now failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function createCron(phrase?: string) {
    if (!cronName.trim() || !model.trim() || !method.trim()) {
      setError("Name, model, and method are required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.bulkCronCreate(connectionId, {
        name: cronName.trim(),
        model: model.trim(),
        method: method.trim(),
        interval_number: intervalNumber,
        interval_type: intervalType,
        active: true,
        confirm_advanced: true,
        confirm_phrase: phrase || CONFIRM_PHRASE,
      });
      setNotice(`Created scheduled action ${cronName.trim()}`);
      setConfirmOpen(false);
      await refreshCrons();
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("create");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Create failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(row: CronRowOut, phrase?: string) {
    if (row.active) {
      setDeactivateTarget(row);
      setConfirmMode("deactivate");
      setConfirmOpen(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.bulkCronPatch(connectionId, row.id, { active: true });
      setNotice(`Activated ${row.name}`);
      await refreshCrons();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDeactivate(phrase?: string) {
    if (!deactivateTarget) return;
    setBusy(true);
    setError(null);
    try {
      await api.bulkCronPatch(connectionId, deactivateTarget.id, {
        active: false,
        confirm_advanced: true,
        confirm_phrase: phrase || CONFIRM_PHRASE,
      });
      setNotice(`Deactivated ${deactivateTarget.name}`);
      setConfirmOpen(false);
      setDeactivateTarget(null);
      await refreshCrons();
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Deactivate failed");
      }
    } finally {
      setBusy(false);
    }
  }

  function onConfirm(phrase: string) {
    if (confirmMode === "run_now") void runNow(false, phrase);
    else if (confirmMode === "create") void createCron(phrase);
    else void confirmDeactivate(phrase);
  }

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap gap-3 text-sm">
          <Link
            href={`/connections/${connectionId}`}
            className="text-[var(--odoo-primary-light)] hover:underline"
          >
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/bulk-suite`}
            className="text-[var(--odoo-primary-light)] hover:underline"
          >
            Bulk Suite
          </Link>
          <Link
            href={`/connections/${connectionId}/power-ops`}
            className="text-[var(--odoo-primary-light)] hover:underline"
          >
            Power Ops
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[var(--odoo-sheet-fg)]">
          Cron Manager
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--odoo-muted)]">
          Plain-language scheduled actions: inspect, run now, toggle, and create jobs that call
          existing model methods only — no raw Python editor.
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />

        {probe && (
          <p className="mt-3 text-xs text-[var(--odoo-muted)]">
            Run-now probe: primary={String(probe.primary)} · fallback={String(probe.fallback)}
            {probe.major != null ? ` · Odoo ${String(probe.major)}` : ""}
          </p>
        )}

        {error && (
          <p className="mt-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </p>
        )}
        {notice && (
          <p className="mt-4 rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-900">
            {notice}
          </p>
        )}

        <section className="odoo-sheet mt-6 space-y-4 p-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="block flex-1 text-sm">
              Search
              <input
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 text-sm"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Name, model, or description"
              />
            </label>
            <label className="block text-sm">
              Status
              <select
                className="mt-1 border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={activeFilter}
                onChange={(e) =>
                  setActiveFilter(e.target.value as "all" | "active" | "inactive")
                }
              >
                <option value="all">All</option>
                <option value="active">Active only</option>
                <option value="inactive">Inactive only</option>
              </select>
            </label>
            <button
              type="button"
              className="odoo-btn-secondary"
              disabled={busy}
              onClick={() => void refreshCrons()}
            >
              Refresh
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--odoo-border)] text-[var(--odoo-muted)]">
                  <th className="py-2 pr-2">Pick</th>
                  <th className="py-2 pr-2">Description</th>
                  <th className="py-2 pr-2">Model</th>
                  <th className="py-2 pr-2">Active</th>
                </tr>
              </thead>
              <tbody>
                {filteredCrons.map((row) => (
                  <tr key={row.id} className="border-b border-[var(--odoo-border)]/60">
                    <td className="py-2 pr-2 align-top">
                      <input
                        type="checkbox"
                        checked={selected.has(row.id)}
                        onChange={() => toggleSelected(row.id)}
                      />
                    </td>
                    <td className="py-2 pr-2 align-top">
                      <div className="font-medium">{row.name}</div>
                      <div className="text-xs text-[var(--odoo-muted)]">{row.description}</div>
                      {row.nextcall && (
                        <div className="text-xs text-[var(--odoo-muted)]">
                          Next: {row.nextcall}
                        </div>
                      )}
                    </td>
                    <td className="py-2 pr-2 align-top font-mono text-xs">
                      {row.model_name || "—"}
                    </td>
                    <td className="py-2 pr-2 align-top">
                      <button
                        type="button"
                        className="text-xs underline"
                        disabled={busy}
                        onClick={() => void toggleActive(row)}
                      >
                        {row.active ? "Active" : "Inactive"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!filteredCrons.length && (
              <p className="py-4 text-sm text-[var(--odoo-muted)]">No scheduled actions match.</p>
            )}
          </div>

          <div className="flex flex-wrap gap-2 pt-2">
            <button
              type="button"
              className="odoo-btn-secondary"
              disabled={busy || !selected.size}
              onClick={() => void runNow(true)}
            >
              Dry run ({selected.size})
            </button>
            <button
              type="button"
              className="odoo-btn-primary"
              disabled={busy || !selected.size}
              onClick={() => void runNow(false)}
            >
              Run now ({selected.size})
            </button>
          </div>
        </section>

        <section className="odoo-sheet mt-6 space-y-4 p-4">
          <h2 className="text-lg font-semibold">Create scheduled action</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Targets an existing public model method — code is generated as{" "}
            <code className="font-mono text-xs">model.method()</code>.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="block text-sm">
              Name
              <input
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={cronName}
                onChange={(e) => setCronName(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              Model
              <input
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                list="cron-manager-models"
              />
              <datalist id="cron-manager-models">
                {models.slice(0, 200).map((m) => (
                  <option key={m.model} value={m.model}>
                    {m.name}
                  </option>
                ))}
              </datalist>
            </label>
            <label className="block text-sm md:col-span-2">
              Method
              <div className="mt-1 flex flex-wrap gap-2">
                <input
                  className="min-w-[12rem] flex-1 border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                  placeholder="action_confirm"
                />
                <button
                  type="button"
                  className="odoo-btn-secondary"
                  disabled={busy || !model.trim()}
                  onClick={() => void discoverMethods()}
                >
                  Discover from form
                </button>
              </div>
              {buttons.length > 0 && (
                <select
                  className="mt-2 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                >
                  {buttons.map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.label} ({b.name})
                    </option>
                  ))}
                </select>
              )}
            </label>
            <label className="block text-sm">
              Every
              <input
                type="number"
                min={1}
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={intervalNumber}
                onChange={(e) => setIntervalNumber(Number(e.target.value) || 1)}
              />
            </label>
            <label className="block text-sm">
              Interval
              <select
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={intervalType}
                onChange={(e) =>
                  setIntervalType(
                    e.target.value as "minutes" | "hours" | "days" | "weeks" | "months",
                  )
                }
              >
                <option value="minutes">Minutes</option>
                <option value="hours">Hours</option>
                <option value="days">Days</option>
                <option value="weeks">Weeks</option>
                <option value="months">Months</option>
              </select>
            </label>
          </div>
          <button
            type="button"
            className="odoo-btn-primary"
            disabled={busy}
            onClick={() => void createCron()}
          >
            Create cron
          </button>
        </section>

        {result && (
          <section className="odoo-sheet mt-6 space-y-2 p-4">
            <h2 className="text-lg font-semibold">Last run</h2>
            <p className="text-sm">{result.message}</p>
            <p className="text-xs text-[var(--odoo-muted)]">
              run_id={result.run_id}
              {result.run_via ? ` · via ${result.run_via}` : ""}
            </p>
            <ul className="text-sm">
              {result.per_record.map((r) => (
                <li key={r.id} className={r.ok ? "text-green-800" : "text-red-800"}>
                  {r.display_name}: {r.ok ? "ok" : r.error}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        phrase={CONFIRM_PHRASE}
        title={
          confirmMode === "deactivate"
            ? "Deactivate scheduled action"
            : confirmMode === "create"
              ? "Create scheduled action"
              : "Run scheduled actions now"
        }
        warning={
          confirmMode === "deactivate"
            ? `Deactivate scheduled action ${deactivateTarget?.name ?? ""}?`
            : confirmMode === "create"
              ? `Create scheduled action on ${model}.${method}()?`
              : `Run ${selected.size} scheduled action(s) immediately?`
        }
        risks={[
          "Executes server-side business logic as the connected Odoo user",
          "May mutate data or send notifications depending on the job",
        ]}
        onConfirm={onConfirm}
        onCancel={() => {
          setConfirmOpen(false);
          setDeactivateTarget(null);
        }}
        busy={busy}
      />
    </main>
  );
}

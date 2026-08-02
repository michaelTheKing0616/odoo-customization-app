"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Connection, ConfirmationRequiredError } from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  isExperimentalMajor,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";

const CONFIRM_PHRASE = "I understand the risks";

const MATCHING_MAJOR_SANDBOX =
  "Sandbox hop uses matching-major ephemeral Docker on :18069 — align staging/prod majors before promote.";

export default function PipelinesPage() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [pipelines, setPipelines] = useState<
    Array<{
      id: string;
      name: string;
      staging_connection_id: string;
      prod_connection_id: string;
      sandbox_connection_id: string | null;
    }>
  >([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hops, setHops] = useState<
    Array<{
      id: string;
      hop: string;
      module_name: string;
      zip_sha256: string;
      status: string;
      message: string;
      validation_id: string | null;
    }>
  >([]);
  const [form, setForm] = useState({
    name: "Default promote path",
    staging_connection_id: "",
    prod_connection_id: "",
  });
  const [zipB64, setZipB64] = useState("");
  const [validationId, setValidationId] = useState<string | null>(null);
  const [pendingHop, setPendingHop] = useState<"sandbox" | "staging" | "prod" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [conns, pipes] = await Promise.all([
      api.listConnections(),
      api.listPipelines(),
    ]);
    setConnections(conns);
    setPipelines(pipes);
    setForm((f) => ({
      ...f,
      staging_connection_id: f.staging_connection_id || conns[0]?.id || "",
      prod_connection_id: f.prod_connection_id || conns[1]?.id || conns[0]?.id || "",
    }));
  }, []);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) {
      setHops([]);
      return;
    }
    api
      .listPipelineHops(selectedId)
      .then(setHops)
      .catch((err: Error) => setError(err.message));
  }, [selectedId]);

  async function onFile(file: File | null) {
    if (!file) return;
    const buf = await file.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    setZipB64(btoa(binary));
    setNotice(`Loaded ${file.name} (${bytes.length} bytes)`);
  }

  async function runHop(hop: "sandbox" | "staging" | "prod", phrase: string) {
    if (!selectedId || !zipB64) {
      setError("Select a pipeline and upload a module zip");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.pipelinePromote(selectedId, {
        hop,
        zip_base64: zipB64,
        validation_id: hop === "sandbox" ? null : validationId,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setNotice(`${hop}: ${res.message}`);
      if (res.validation_id) setValidationId(res.validation_id);
      setPendingHop(null);
      const nextHops = await api.listPipelineHops(selectedId);
      setHops(nextHops);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setPendingHop(hop);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Promote failed");
      }
    } finally {
      setBusy(false);
    }
  }

  const connName = (id: string) => connections.find((c) => c.id === id)?.name ?? id;

  const focusStagingId = useMemo(() => {
    const sel = pipelines.find((p) => p.id === selectedId);
    return sel?.staging_connection_id ?? form.staging_connection_id;
  }, [pipelines, selectedId, form.staging_connection_id]);

  const focusConnection = useMemo(
    () => connections.find((c) => c.id === focusStagingId) ?? null,
    [connections, focusStagingId],
  );

  const pipelineCaveat = isExperimentalMajor(focusConnection?.capabilities)
    ? `Experimental major: ${MATCHING_MAJOR_SANDBOX}`
    : MATCHING_MAJOR_SANDBOX;

  const canPromote = mutationAllowed(focusConnection);
  const promoteBlocked = mutationBlockedReason(focusConnection);

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link href="/" className="text-[#c9a9c0] hover:underline">
            ← Home
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Multi-env promote
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          Sandbox (ephemeral) → staging connection → Online / prod connection. Same zip
          sha256 required across hops.
        </p>
        <VersionAwarenessBanner
          capabilities={focusConnection?.capabilities}
          caveat={pipelineCaveat}
        />
        {promoteBlocked && (
          <p className="mt-2 text-sm text-[#e8d09f]">{promoteBlocked}</p>
        )}

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}
        {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}

        <form
          className="mt-8 space-y-3 border border-[#3d2a38] bg-[#0f1a16]/70 p-5"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              const created = await api.createPipeline(form);
              setNotice(`Created pipeline ${created.name}`);
              await refresh();
              setSelectedId(created.id);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Create failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          <h2 className="font-[family-name:var(--font-display)] text-xl">New pipeline</h2>
          <input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
          />
          <label className="block text-sm">
            <span className="text-[#a8909e]">Staging connection</span>
            <select
              required
              value={form.staging_connection_id}
              onChange={(e) =>
                setForm({ ...form, staging_connection_id: e.target.value })
              }
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            >
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-[#a8909e]">Prod connection</span>
            <select
              required
              value={form.prod_connection_id}
              onChange={(e) => setForm({ ...form, prod_connection_id: e.target.value })}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            >
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={busy || connections.length < 1}
            className="h-10 bg-[#714B67] px-4 text-sm font-semibold text-white"
          >
            Create pipeline
          </button>
        </form>

        <section className="mt-8 border border-[#3d2a38] p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl">Pipelines</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {pipelines.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(p.id)}
                  className={`w-full border px-3 py-2 text-left ${
                    selectedId === p.id
                      ? "border-[#c9a9c0] bg-[#0f1a16]"
                      : "border-[#3d2a38]"
                  }`}
                >
                  <span className="font-medium">{p.name}</span>
                  <span className="mt-1 block text-xs text-[#8f7a88]">
                    staging={connName(p.staging_connection_id)} · prod=
                    {connName(p.prod_connection_id)}
                  </span>
                </button>
              </li>
            ))}
          </ul>

          {selectedId && (
            <div className="mt-6 space-y-3">
              <label className="block text-sm">
                <span className="text-[#a8909e]">Module zip</span>
                <input
                  type="file"
                  accept=".zip"
                  className="mt-1 block w-full text-sm"
                  onChange={(e) => void onFile(e.target.files?.[0] ?? null)}
                />
              </label>
              {validationId && (
                <p className="font-mono text-xs text-[#8f7a88]">
                  validation_id={validationId}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {(["sandbox", "staging", "prod"] as const).map((hop) => (
                  <button
                    key={hop}
                    type="button"
                    disabled={busy || !zipB64 || !canPromote}
                    title={promoteBlocked ?? undefined}
                    onClick={() => setPendingHop(hop)}
                    className="border border-[#c9a9c0] px-3 py-2 text-sm capitalize text-[#c9a9c0] disabled:opacity-40"
                  >
                    {hop === "sandbox" ? "1. Sandbox" : hop === "staging" ? "2. Staging" : "3. Prod"}
                  </button>
                ))}
              </div>
              <ul className="max-h-48 space-y-1 overflow-auto text-xs text-[#8f7a88]">
                {hops.map((h) => (
                  <li key={h.id} className="border-t border-[#1e2f29] py-1 font-mono">
                    {h.hop} · {h.status} · {h.module_name} · {h.zip_sha256.slice(0, 10)}…
                    <span className="block text-[#a8909e]">{h.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={!!pendingHop}
        title={`Promote: ${pendingHop}`}
        warning="Installs the module zip on the selected hop target."
        risks={[
          "Sandbox uses ephemeral Docker",
          "Staging installs on the staging connection",
          "Prod requires a successful staging hop for this zip",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setPendingHop(null)}
        onConfirm={(phrase) => {
          if (pendingHop) void runHop(pendingHop, phrase);
        }}
      />
    </main>
  );
}

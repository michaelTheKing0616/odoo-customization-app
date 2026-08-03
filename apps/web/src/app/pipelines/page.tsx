"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Connection, ConfirmationRequiredError } from "@/lib/api";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  isExperimentalMajor,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

const CONFIRM_PHRASE = "I understand the risks";

const MATCHING_MAJOR_SANDBOX =
  "Sandbox hop uses matching-major ephemeral Docker on :18069 — align staging/prod majors before promote.";

const HOPS = [
  { id: "sandbox" as const, step: 1, label: "Sandbox", desc: "Ephemeral Docker gate" },
  { id: "staging" as const, step: 2, label: "Staging", desc: "Staging connection install" },
  { id: "prod" as const, step: 3, label: "Prod", desc: "Production connection install" },
];

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

  const selectedPipeline = pipelines.find((p) => p.id === selectedId);

  return (
    <div className="mx-auto max-w-5xl" data-testid="pipelines-page">
      <PageHeader
        title="Multi-env promote"
        description="Sandbox (ephemeral) → staging connection → prod connection. Same zip sha256 required across hops."
      />
      <VersionAwarenessBanner
        capabilities={focusConnection?.capabilities}
        caveat={pipelineCaveat}
      />
      {promoteBlocked ? (
        <Callout variant="warning" title="Promote blocked" className="mt-4">
          {promoteBlocked}
        </Callout>
      ) : null}

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      <Card className="mt-8 p-5">
        <form
          className="space-y-4"
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
          <h2 className="text-xl font-semibold text-ink">New pipeline</h2>
          <Input
            label="Name"
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Select
            label="Staging connection"
            required
            options={connections.map((c) => ({ value: c.id, label: c.name }))}
            value={form.staging_connection_id}
            onChange={(e) =>
              setForm({ ...form, staging_connection_id: e.target.value })
            }
          />
          <Select
            label="Prod connection"
            required
            options={connections.map((c) => ({ value: c.id, label: c.name }))}
            value={form.prod_connection_id}
            onChange={(e) => setForm({ ...form, prod_connection_id: e.target.value })}
          />
          <Button
            type="submit"
            variant="primary"
            disabled={busy || connections.length < 1}
            loading={busy}
          >
            Create pipeline
          </Button>
        </form>
      </Card>

      <section className="mt-8">
        <h2 className="text-xl font-semibold text-ink">Pipelines</h2>
        <ul className="mt-3 space-y-2">
          {pipelines.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => setSelectedId(p.id)}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                  selectedId === p.id
                    ? "border-accent bg-accent-subtle/20"
                    : "border-border-subtle bg-surface"
                }`}
              >
                <span className="font-medium text-ink">{p.name}</span>
                <span className="mt-1 block text-xs text-muted">
                  staging={connName(p.staging_connection_id)} · prod=
                  {connName(p.prod_connection_id)}
                </span>
              </button>
            </li>
          ))}
        </ul>

        {selectedPipeline ? (
          <div className="mt-6 space-y-4">
            <Card className="p-4">
              <label className="block text-sm">
                <span className="font-medium text-ink">Module zip</span>
                <input
                  type="file"
                  accept=".zip"
                  className="mt-2 block w-full text-sm"
                  onChange={(e) => void onFile(e.target.files?.[0] ?? null)}
                />
              </label>
              {validationId ? (
                <p className="mt-2 font-mono text-xs text-muted">
                  validation_id={validationId}
                </p>
              ) : null}
            </Card>

            <div className="grid gap-3 md:grid-cols-3">
              {HOPS.map((hop) => {
                const hopHistory = hops.filter((h) => h.hop === hop.id);
                const last = hopHistory[hopHistory.length - 1];
                return (
                  <Card key={hop.id} className="flex flex-col p-4">
                    <div className="flex items-center gap-2">
                      <Badge variant="info">{hop.step}</Badge>
                      <h3 className="font-semibold text-ink">{hop.label}</h3>
                    </div>
                    <p className="mt-1 text-xs text-muted">{hop.desc}</p>
                    {last ? (
                      <p className="mt-2 text-xs">
                        <Badge
                          variant={
                            last.status === "ok" || last.status === "complete"
                              ? "success"
                              : "warning"
                          }
                        >
                          {last.status}
                        </Badge>
                        <span className="ml-2 font-mono text-muted">
                          {last.zip_sha256.slice(0, 10)}…
                        </span>
                      </p>
                    ) : (
                      <p className="mt-2 text-xs text-muted">No hops yet</p>
                    )}
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="mt-auto pt-4"
                      disabled={busy || !zipB64 || !canPromote}
                      title={promoteBlocked ?? undefined}
                      onClick={() => setPendingHop(hop.id)}
                    >
                      Promote to {hop.label}
                    </Button>
                  </Card>
                );
              })}
            </div>

            {hops.length > 0 ? (
              <Card className="max-h-48 overflow-auto p-4">
                <h3 className="text-sm font-semibold text-ink">Hop history</h3>
                <ul className="mt-2 space-y-1 font-mono text-xs text-muted">
                  {hops.map((h) => (
                    <li key={h.id} className="border-t border-border-subtle py-1">
                      {h.hop} · {h.status} · {h.module_name} · {h.zip_sha256.slice(0, 10)}…
                      <span className="block text-muted">{h.message}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}
          </div>
        ) : null}
      </section>

      <ConfirmDialogV2
        open={!!pendingHop}
        riskLevel="danger"
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
    </div>
  );
}

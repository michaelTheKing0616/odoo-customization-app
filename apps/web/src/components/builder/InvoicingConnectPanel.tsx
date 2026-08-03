"use client";

import { useEffect, useState } from "react";
import { api, ConfirmationRequiredError, type Connection, type InvoicingPreflightOut } from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const CONFIRM_PHRASE = "I understand the risks";

export function InvoicingConnectPanel({
  connectionId,
  connection,
  defaultModel,
}: {
  connectionId: string;
  connection: Connection | null;
  defaultModel?: string;
}) {
  const [preflight, setPreflight] = useState<InvoicingPreflightOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmMode, setConfirmMode] = useState<"connect" | "draft">("connect");

  const [model, setModel] = useState(defaultModel ?? "");
  const [invoiceField, setInvoiceField] = useState("x_invoice_ids");
  const [partnerField, setPartnerField] = useState("x_partner_id");
  const [amountField, setAmountField] = useState("x_amount");
  const [descriptionField, setDescriptionField] = useState("x_name");
  const [recordId, setRecordId] = useState("");
  const [moduleSpec, setModuleSpec] = useState<string>("");

  useEffect(() => {
    api
      .getInvoicingPreflight(connectionId)
      .then(setPreflight)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  useEffect(() => {
    if (defaultModel) setModel(defaultModel);
  }, [defaultModel]);

  const accountOk = preflight?.account_installed === true;
  const l10nOk = preflight?.l10n_installed === true;
  const major = connection?.capabilities?.major;

  async function runConnect(phrase?: string) {
    if (!model.startsWith("x_")) {
      setError("Model must be a custom x_* workflow model");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.connectInvoicing(connectionId, {
        model,
        invoice_field: invoiceField,
        confirm_advanced: true,
        confirm_phrase: phrase || CONFIRM_PHRASE,
      });
      setNotice(
        `${res.field_created ? "Created" : "Reused"} ${res.invoice_field}; window action #${res.window_action_id}`,
      );
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("connect");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Connect failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function runDraft(phrase?: string) {
    if (!recordId.trim()) {
      setError("Record id required for draft invoice");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.createDraftInvoice(connectionId, {
        source_model: model,
        record_id: Number(recordId),
        invoice_field: invoiceField,
        partner_field: partnerField,
        amount_field: amountField,
        description_field: descriptionField,
        confirm_advanced: true,
        confirm_phrase: phrase || CONFIRM_PHRASE,
      });
      setNotice(`Draft ${res.move_name ?? res.move_id} linked to ${model}/${res.record_id}`);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("draft");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Draft invoice failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function loadModuleSpec() {
    if (!model.startsWith("x_")) {
      setError("Model must be custom x_* for module spec");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.getInvoicingModuleSpec(connectionId, {
        model,
        invoice_field: invoiceField,
        partner_field: partnerField,
      });
      setModuleSpec(JSON.stringify(res.fragment, null, 2));
      setNotice("Module-path fragment ready (includes account dependency + review note).");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Module spec failed");
    } finally {
      setBusy(false);
    }
  }

  async function mergeIntoModuleSpecDraft() {
    if (!model.startsWith("x_")) {
      setError("Model must be custom x_* to merge");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const draftKey = `modulespec-draft:${connectionId}`;
      let base: Record<string, unknown> = {};
      try {
        const raw = sessionStorage.getItem(draftKey);
        if (raw) base = JSON.parse(raw) as Record<string, unknown>;
      } catch {
        base = {};
      }
      const res = await api.mergeInvoicingIntoSpec(connectionId, {
        base_spec: base,
        model,
        invoice_field: invoiceField,
        partner_field: partnerField,
      });
      sessionStorage.setItem(draftKey, JSON.stringify(res.merged));
      setModuleSpec(JSON.stringify(res.merged, null, 2));
      setNotice("Merged invoicing fragment into ModuleSpec session draft — open ModuleSpec editor to export.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Merge failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-8 border border-[#E5E5E5] bg-white p-6">
      <h2 className="text-lg font-semibold text-[#212529]">Connect to Invoicing (§19)</h2>
      <p className="mt-1 text-sm text-[#6C757D]">
        Live path: many2many on your custom model only. Module export may add inverse m2o on{" "}
        <code className="text-xs">account.move</code>. Draft invoices never post.
      </p>

      {preflight && !preflight.ok && (
        <div className="mt-4 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          {preflight.message}
          {preflight.l10n_modules.length > 0 && (
            <span className="block mt-1">Installed l10n: {preflight.l10n_modules.join(", ")}</span>
          )}
        </div>
      )}

      {preflight?.ok && (
        <p className="mt-3 text-sm text-green-800">
          Accounting + l10n detected
          {preflight.company_country ? ` (${preflight.company_country})` : ""}.
        </p>
      )}

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="block text-sm">
          Workflow model
          <input
            className="mt-1 w-full border px-3 py-2 text-sm"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="x_matter"
          />
        </label>
        <label className="block text-sm">
          Invoice m2m field
          <input
            className="mt-1 w-full border px-3 py-2 text-sm"
            value={invoiceField}
            onChange={(e) => setInvoiceField(e.target.value)}
          />
        </label>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="block text-sm">
          Partner field (mapping)
          <input
            className="mt-1 w-full border px-3 py-2 text-sm"
            value={partnerField}
            onChange={(e) => setPartnerField(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          Amount field
          <input
            className="mt-1 w-full border px-3 py-2 text-sm"
            value={amountField}
            onChange={(e) => setAmountField(e.target.value)}
          />
        </label>
        <label className="block text-sm md:col-span-2">
          Description field
          <input
            className="mt-1 w-full border px-3 py-2 text-sm"
            value={descriptionField}
            onChange={(e) => setDescriptionField(e.target.value)}
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy || !accountOk}
          onClick={() => void runConnect()}
          className="h-10 bg-[#714B67] px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          Connect live (m2m)
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void loadModuleSpec()}
          className="h-10 border px-4 text-sm font-semibold disabled:opacity-50"
        >
          Preview module spec
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void mergeIntoModuleSpecDraft()}
          className="h-10 border px-4 text-sm font-semibold disabled:opacity-50"
        >
          Merge into ModuleSpec draft
        </button>
      </div>

      <div className="mt-6 border-t pt-4">
        <h3 className="text-sm font-semibold">Create draft invoice</h3>
        <p className="text-xs text-[#6C757D]">
          Maps partner / amount / description → draft out_invoice; requires l10n preflight OK.
        </p>
        <label className="mt-2 block text-sm">
          Record id
          <input
            className="mt-1 w-full max-w-xs border px-3 py-2 text-sm"
            value={recordId}
            onChange={(e) => setRecordId(e.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={busy || !l10nOk}
          onClick={() => void runDraft()}
          className="mt-3 h-10 bg-[#212529] px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          Create draft invoice
        </button>
      </div>

      {moduleSpec && (
        <pre className="mt-4 max-h-64 overflow-auto bg-[#F8F9FA] p-3 text-xs">{moduleSpec}</pre>
      )}

      {notice && <p className="mt-3 text-sm text-green-700">{notice}</p>}
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      {major != null && (
        <p className="mt-2 text-xs text-[#6C757D]">Odoo major {major} — GA invoicing on 17–19.</p>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title={confirmMode === "connect" ? "Connect to Invoicing" : "Create draft invoice"}
        warning={error ?? "Confirm live Odoo mutation."}
        risks={[
          "Writes to live Odoo metadata or account.move",
          "Draft only — never posts from this flow",
          "Verify fiscal localization before go-live",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) =>
          void (confirmMode === "connect" ? runConnect(phrase) : runDraft(phrase))
        }
      />
    </section>
  );
}

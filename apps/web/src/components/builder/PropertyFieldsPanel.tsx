"use client";

import { useEffect, useState } from "react";
import { api, ConfirmationRequiredError, type Connection, type PropertyFieldsProbeOut } from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const CONFIRM_PHRASE = "I understand the risks";

const PROPERTY_TYPES = [
  "char",
  "boolean",
  "integer",
  "float",
  "date",
  "datetime",
  "selection",
  "tags",
  "many2one",
  "many2many",
] as const;

type PropertyEntry = {
  name: string;
  string: string;
  type: string;
  default: string;
  selection: string;
  comodel: string;
};

const EMPTY_ENTRY = (): PropertyEntry => ({
  name: "",
  string: "",
  type: "char",
  default: "",
  selection: "",
  comodel: "",
});

export function PropertyFieldsPanel({
  connectionId,
  connection,
  defaultChildModel,
}: {
  connectionId: string;
  connection: Connection | null;
  defaultChildModel?: string;
}) {
  const [probe, setProbe] = useState<PropertyFieldsProbeOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmMode, setConfirmMode] = useState<"setup" | "definition">("setup");

  const [childModel, setChildModel] = useState(defaultChildModel ?? "");
  const [parentM2o, setParentM2o] = useState("x_parent_id");
  const [propertiesField, setPropertiesField] = useState("x_properties");
  const [definitionField, setDefinitionField] = useState("x_properties_definition");
  const [parentModel, setParentModel] = useState("");
  const [parentRecordId, setParentRecordId] = useState("");
  const [entries, setEntries] = useState<PropertyEntry[]>([EMPTY_ENTRY()]);

  useEffect(() => {
    api
      .getPropertyFieldsProbe(connectionId)
      .then(setProbe)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  useEffect(() => {
    if (defaultChildModel) setChildModel(defaultChildModel);
  }, [defaultChildModel]);

  const supported = probe?.supported === true;
  const major = connection?.capabilities?.major ?? probe?.major;

  async function runSetup(phrase?: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.setupPropertyFields(connectionId, {
        child_model: childModel,
        parent_m2o_field: parentM2o,
        properties_field: propertiesField,
        definition_field: definitionField,
        confirm_advanced: true,
        confirm_phrase: phrase || CONFIRM_PHRASE,
      });
      setParentModel(res.parent_model);
      setNotice(
        `${res.created ? "Created" : "Exists"} ${res.properties_field} on ${childModel} → ${res.parent_model}.${res.definition_field}`,
      );
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("setup");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Setup failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function runDefinitionWrite(phrase?: string) {
    if (!parentModel || !parentRecordId) {
      setError("Parent model and record id required");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payloadEntries = entries
        .filter((e) => e.name.trim())
        .map((e) => ({
          name: e.name.trim(),
          string: e.string.trim() || undefined,
          type: e.type,
          default: e.default || undefined,
          selection:
            e.type === "selection" && e.selection.trim()
              ? e.selection.split(",").map((pair) => {
                  const [v, l] = pair.split(":").map((s) => s.trim());
                  return [v || pair.trim(), l || v || pair.trim()];
                })
              : undefined,
          comodel: e.comodel.trim() || undefined,
        }));
      const res = await api.writePropertyDefinition(connectionId, {
        parent_model: parentModel,
        parent_record_id: Number(parentRecordId),
        definition_field: definitionField,
        entries: payloadEntries,
        confirm_advanced: true,
        confirm_phrase: phrase || CONFIRM_PHRASE,
      });
      setNotice(`Wrote ${res.property_count} property definition(s) on record ${res.record_id}`);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMode("definition");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Definition write failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="odoo-sheet mt-6 space-y-4 p-4" data-testid="property-fields-panel">
      <h2 className="text-sm font-semibold text-[var(--odoo-primary)]">Properties field (§18)</h2>
      <p className="text-xs text-[var(--odoo-muted)]">
        Same field everywhere on every record → use a <strong>regular field</strong>. Different
        values per parent record → use a <strong>Properties</strong> field bound to a parent m2o.
      </p>
      {!probe && <p className="text-xs text-[var(--odoo-muted)]">Probing Odoo major…</p>}
      {probe && !supported && (
        <p className="border border-[var(--odoo-border)] bg-[#fff8e6] px-3 py-2 text-xs text-[#6b4e00]">
          Properties fields are not supported on Odoo {major ?? probe.major} (probe: {probe.source}
          ). Use regular custom fields instead.
        </p>
      )}
      {probe && supported && (
        <>
          <p className="text-xs text-[var(--odoo-success)]">
            Supported on Odoo {probe.major} ({probe.source} probe).
          </p>
          <div className="grid gap-3 sm:grid-cols-2 text-sm">
            <label>
              Child model
              <input
                value={childModel}
                onChange={(e) => setChildModel(e.target.value)}
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
              />
            </label>
            <label>
              Parent m2o field
              <input
                value={parentM2o}
                onChange={(e) => setParentM2o(e.target.value)}
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
              />
            </label>
            <label>
              Properties field
              <input
                value={propertiesField}
                onChange={(e) => setPropertiesField(e.target.value)}
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
              />
            </label>
            <label>
              Definition field (parent)
              <input
                value={definitionField}
                onChange={(e) => setDefinitionField(e.target.value)}
                className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
              />
            </label>
          </div>
          <button
            type="button"
            disabled={busy || !childModel || !parentM2o}
            onClick={() => {
              setConfirmMode("setup");
              setConfirmOpen(true);
            }}
            className="bg-[var(--odoo-primary)] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Create properties field pair
          </button>

          <div className="border-t border-[var(--odoo-border)] pt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--odoo-muted)]">
              Definition editor (parent record)
            </h3>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <label className="text-sm">
                Parent model
                <input
                  value={parentModel}
                  onChange={(e) => setParentModel(e.target.value)}
                  className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
                />
              </label>
              <label className="text-sm">
                Parent record id
                <input
                  value={parentRecordId}
                  onChange={(e) => setParentRecordId(e.target.value)}
                  className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs"
                />
              </label>
            </div>
            <ul className="mt-3 space-y-2">
              {entries.map((entry, idx) => (
                <li key={idx} className="grid gap-2 sm:grid-cols-4 text-xs">
                  <input
                    placeholder="name"
                    value={entry.name}
                    onChange={(e) =>
                      setEntries((rows) =>
                        rows.map((r, i) => (i === idx ? { ...r, name: e.target.value } : r)),
                      )
                    }
                    className="border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono"
                  />
                  <input
                    placeholder="label"
                    value={entry.string}
                    onChange={(e) =>
                      setEntries((rows) =>
                        rows.map((r, i) => (i === idx ? { ...r, string: e.target.value } : r)),
                      )
                    }
                    className="border border-[var(--odoo-border)] bg-white px-2 py-1"
                  />
                  <select
                    value={entry.type}
                    onChange={(e) =>
                      setEntries((rows) =>
                        rows.map((r, i) => (i === idx ? { ...r, type: e.target.value } : r)),
                      )
                    }
                    className="border border-[var(--odoo-border)] bg-white px-2 py-1"
                  >
                    {PROPERTY_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                  <input
                    placeholder={entry.type === "selection" ? "a:A,b:B" : "default"}
                    value={entry.type === "selection" ? entry.selection : entry.default}
                    onChange={(e) =>
                      setEntries((rows) =>
                        rows.map((r, i) =>
                          i === idx
                            ? entry.type === "selection"
                              ? { ...r, selection: e.target.value }
                              : { ...r, default: e.target.value }
                            : r,
                        ),
                      )
                    }
                    className="border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono"
                  />
                </li>
              ))}
            </ul>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                className="border border-[var(--odoo-primary)] px-2 py-1 text-xs text-[var(--odoo-primary)]"
                onClick={() => setEntries((rows) => [...rows, EMPTY_ENTRY()])}
              >
                Add property
              </button>
              <button
                type="button"
                disabled={busy || !parentModel || !parentRecordId}
                onClick={() => {
                  setConfirmMode("definition");
                  setConfirmOpen(true);
                }}
                className="bg-[var(--odoo-primary)] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
              >
                Write definition
              </button>
            </div>
          </div>
        </>
      )}
      {notice && <p className="text-sm text-[var(--odoo-success)]">{notice}</p>}
      {error && <p className="text-sm text-[var(--odoo-danger)]">{error}</p>}

      <ConfirmDialog
        open={confirmOpen}
        title={confirmMode === "setup" ? "Create properties fields" : "Write property definition"}
        warning={
          confirmMode === "setup"
            ? `Create Properties field on ${childModel}.`
            : `Write definition on ${parentModel} #${parentRecordId}.`
        }
        risks={[
          "Live ir.model.fields / record writes on this Odoo database",
          "Probe must pass for your Odoo major",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) =>
          void (confirmMode === "setup" ? runSetup(phrase) : runDefinitionWrite(phrase))
        }
      />
    </section>
  );
}

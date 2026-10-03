"use client";

import { api } from "@/lib/api";
import type { ConfigPageModel } from "./use-config-page";

export function ConfigMailPaperDefaults({ vm }: { vm: ConfigPageModel }) {
  const {
    connectionId,
    mailTemplates,
    mailForm,
    setMailForm,
    activityTypes,
    activityName,
    setActivityName,
    paperformats,
    paperForm,
    setPaperForm,
    defaults,
    defaultModel,
    setDefaultModel,
    defaultField,
    setDefaultField,
    defaultValue,
    setDefaultValue,
    busy,
    setBusy,
    setError,
    setNotice,
    refresh,
  } = vm;

  return (
    <>
        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="rounded-md border border-border-subtle bg-surface p-5">
            <h2 className="text-ui-title">Mail templates</h2>
            <form
              className="mt-3 space-y-2"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                try {
                  await api.createConfigMailTemplate(connectionId, mailForm);
                  setNotice("Mail template created");
                  setMailForm((f) => ({ ...f, name: "" }));
                  await refresh();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Create failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              {(
                [
                  ["name", "Name"],
                  ["model", "Model"],
                  ["subject", "Subject"],
                  ["email_to", "Email to"],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="block text-xs">
                  <span className="text-muted">{label}</span>
                  <input
                    required={key !== "email_to"}
                    value={mailForm[key]}
                    onChange={(e) => setMailForm({ ...mailForm, [key]: e.target.value })}
                    className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 text-sm"
                  />
                </label>
              ))}
              <label className="block text-xs">
                <span className="text-muted">Body HTML</span>
                <textarea
                  required
                  value={mailForm.body_html}
                  onChange={(e) =>
                    setMailForm({ ...mailForm, body_html: e.target.value })
                  }
                  rows={3}
                  className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 font-mono text-xs"
                />
              </label>
              <button
                type="submit"
                disabled={busy}
                className="h-9 bg-accent px-3 text-sm font-semibold text-white"
              >
                Create template
              </button>
            </form>
            <ul className="mt-4 max-h-48 space-y-1 overflow-auto text-xs text-muted">
              {mailTemplates.map((t) => (
                <li key={t.id}>
                  #{t.id} {t.name} · {t.model} · {t.subject}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-md border border-border-subtle bg-surface p-5">
            <h2 className="text-ui-title">Activity types</h2>
            <form
              className="mt-3 flex gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                try {
                  await api.createConfigActivityType(connectionId, {
                    name: activityName,
                  });
                  setActivityName("");
                  setNotice("Activity type created");
                  await refresh();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Create failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              <input
                required
                value={activityName}
                onChange={(e) => setActivityName(e.target.value)}
                placeholder="Type name"
                className="flex-1 rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 text-sm"
              />
              <button
                type="submit"
                disabled={busy}
                className="border border-accent px-3 text-sm text-muted"
              >
                Add
              </button>
            </form>
            <ul className="mt-4 max-h-48 space-y-1 overflow-auto text-xs text-muted">
              {activityTypes.map((a) => (
                <li key={a.id}>
                  #{a.id} {a.name}
                  {a.summary ? ` — ${a.summary}` : ""}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="rounded-md border border-border-subtle bg-surface p-5">
            <h2 className="text-ui-title">Paperformats</h2>
            <form
              className="mt-3 flex flex-wrap gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                try {
                  await api.upsertConfigPaperformat(connectionId, {
                    name: paperForm.name,
                    format: paperForm.format,
                    margin_top: paperForm.margin_top,
                  });
                  setPaperForm({ name: "", format: "A4", margin_top: 40 });
                  setNotice("Paperformat saved");
                  await refresh();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Save failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              <input
                required
                placeholder="Name"
                value={paperForm.name}
                onChange={(e) => setPaperForm({ ...paperForm, name: e.target.value })}
                className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1 text-sm"
              />
              <input
                placeholder="format"
                value={paperForm.format}
                onChange={(e) => setPaperForm({ ...paperForm, format: e.target.value })}
                className="w-24 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-sm"
              />
              <button
                type="submit"
                disabled={busy}
                className="border border-accent px-3 text-sm text-muted"
              >
                Create
              </button>
            </form>
            <ul className="mt-4 max-h-40 space-y-1 overflow-auto text-xs text-muted">
              {paperformats.map((p) => (
                <li key={p.id}>
                  #{p.id} {p.name} · {p.format} · top {p.margin_top}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-md border border-border-subtle bg-surface p-5">
            <h2 className="text-ui-title">Field defaults</h2>
            <p className="mt-1 text-xs text-muted">ir.default for a model</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <input
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
                className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-sm"
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void refresh()}
                className="border border-border-subtle px-3 text-sm"
              >
                Load
              </button>
            </div>
            <form
              className="mt-3 flex flex-wrap gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                try {
                  await api.upsertIrDefault(connectionId, {
                    model: defaultModel,
                    field_name: defaultField,
                    value: defaultValue,
                  });
                  setNotice(`Default set for ${defaultModel}.${defaultField}`);
                  await refresh();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Upsert failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              <input
                required
                placeholder="field"
                value={defaultField}
                onChange={(e) => setDefaultField(e.target.value)}
                className="w-28 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-sm"
              />
              <input
                required
                placeholder="value"
                value={defaultValue}
                onChange={(e) => setDefaultValue(e.target.value)}
                className="flex-1 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 text-sm"
              />
              <button
                type="submit"
                disabled={busy}
                className="border border-accent px-3 text-sm text-muted"
              >
                Upsert
              </button>
            </form>
            <ul className="mt-4 max-h-40 space-y-1 overflow-auto text-xs text-muted">
              {defaults.map((d) => (
                <li key={d.id}>
                  #{d.id} {d.field_name} = {d.json_value}
                </li>
              ))}
            </ul>
          </div>
        </section>
    </>
  );
}

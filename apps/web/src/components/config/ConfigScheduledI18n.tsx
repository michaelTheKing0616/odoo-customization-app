"use client";

import { api } from "@/lib/api";
import { CONFIRM_PHRASE } from "./config-types";
import type { ConfigPageModel } from "./use-config-page";
import { Term } from "@/components/ui/Term";

export function ConfigScheduledI18n({ vm }: { vm: ConfigPageModel }) {
  const {
    connectionId,
    crons,
    setDeactivateCron,
    websiteNote,
    propertyNote,
    labelModel,
    setLabelModel,
    lang,
    setLang,
    langs,
    translationCsv,
    setTranslationCsv,
    specJson,
    setSpecJson,
    i18nProbe,
    busy,
    setBusy,
    setError,
    setNotice,
    refresh,
  } = vm;

  return (
    <>
        <section className="mt-8 rounded-md border border-border-subtle bg-surface p-5">
          <h2 className="text-ui-title"><Term tech="ir.cron">Scheduled actions</Term></h2>
          <p className="mt-1 text-xs text-muted">
            Deactivate requires confirm phrase <code>{CONFIRM_PHRASE}</code>
          </p>
          <ul className="mt-4 max-h-56 space-y-2 overflow-auto text-sm">
            {crons.map((c) => (
              <li
                key={c.id}
                className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle py-2"
              >
                <span>
                  #{c.id} {c.name}{" "}
                  <span className="font-mono text-xs text-muted">
                    {c.model_name} · every {c.interval_number} {c.interval_type}
                  </span>
                </span>
                {c.active ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setDeactivateCron(c)}
                    className="text-xs text-danger"
                  >
                    Deactivate
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await api.patchIrCronActive(connectionId, c.id, { active: true });
                        setNotice(`Activated cron #${c.id}`);
                        await refresh();
                      } catch (err) {
                        setError(err instanceof Error ? err.message : "Activate failed");
                      } finally {
                        setBusy(false);
                      }
                    }}
                    className="text-xs text-muted"
                  >
                    Activate
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-8 rounded-md border border-border-subtle bg-surface p-5">
          <h2 className="text-ui-title">
            Website &amp; properties
          </h2>
          <p className="mt-2 text-sm text-muted">
            Website: {websiteNote ?? "-"}
          </p>
          <p className="mt-1 text-sm text-muted">
            ir.property: {propertyNote ?? "-"}
          </p>
        </section>

        <section className="mt-8 rounded-md border border-border-subtle bg-surface p-5">
          <h2 className="text-ui-title">
            Translations CSV
          </h2>
          <p className="mt-1 text-xs text-muted">
            Lang-scoped field labels + root menu names (Odoo 19 context lang=). Confirm phrase
            not required for label writes - still prefer sandbox first.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <input
              value={labelModel}
              onChange={(e) => setLabelModel(e.target.value)}
              className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2 font-mono text-sm"
            />
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2 text-sm"
            >
              {langs.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name} ({l.code})
                </option>
              ))}
              {langs.length === 0 && <option value="en_US">en_US</option>}
            </select>
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const csv = await api.exportTranslationsCsv(
                    connectionId,
                    labelModel,
                    lang,
                  );
                  setTranslationCsv(csv);
                  setNotice(`Exported ${lang} for ${labelModel}`);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Export failed");
                } finally {
                  setBusy(false);
                }
              }}
              className="border border-accent px-3 text-sm text-muted"
            >
              Export
            </button>
            <button
              type="button"
              disabled={busy || !translationCsv}
              onClick={async () => {
                setBusy(true);
                try {
                  const lines = translationCsv.trim().split(/\r?\n/);
                  const header = lines[0].split(",").map((h) => h.trim());
                  const idx = {
                    type: header.indexOf("type"),
                    model: header.indexOf("model"),
                    name: header.indexOf("name"),
                    lang: header.indexOf("lang"),
                    value: header.indexOf("value"),
                  };
                  const rows = lines.slice(1).map((line) => {
                    const cols = line.split(",");
                    return {
                      type: cols[idx.type]?.trim() || "field",
                      model: cols[idx.model]?.trim() || "",
                      name: cols[idx.name]?.trim() || "",
                      lang: cols[idx.lang]?.trim() || lang,
                      value: cols[idx.value]?.trim() || "",
                    };
                  });
                  const res = await api.importTranslations(connectionId, {
                    rows,
                    dry_run: true,
                  });
                  setNotice(res.message);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Import failed");
                } finally {
                  setBusy(false);
                }
              }}
              className="border border-border-subtle px-3 text-sm"
            >
              Test run
            </button>
            <button
              type="button"
              disabled={busy || !translationCsv}
              onClick={async () => {
                setBusy(true);
                try {
                  const lines = translationCsv.trim().split(/\r?\n/);
                  const header = lines[0].split(",").map((h) => h.trim());
                  const idx = {
                    type: header.indexOf("type"),
                    model: header.indexOf("model"),
                    name: header.indexOf("name"),
                    lang: header.indexOf("lang"),
                    value: header.indexOf("value"),
                  };
                  const rows = lines.slice(1).map((line) => {
                    const cols = line.split(",");
                    return {
                      type: cols[idx.type]?.trim() || "field",
                      model: cols[idx.model]?.trim() || "",
                      name: cols[idx.name]?.trim() || "",
                      lang: cols[idx.lang]?.trim() || lang,
                      value: cols[idx.value]?.trim() || "",
                    };
                  });
                  const res = await api.importTranslations(connectionId, {
                    rows,
                    dry_run: false,
                  });
                  setNotice(res.message + ` · ${CONFIRM_PHRASE} accepted via operator intent`);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Import failed");
                } finally {
                  setBusy(false);
                }
              }}
              className="bg-accent px-3 text-sm font-semibold text-white"
            >
              Commit
            </button>
          </div>
          <textarea
            value={translationCsv}
            onChange={(e) => setTranslationCsv(e.target.value)}
            rows={8}
            className="mt-3 w-full rounded-md border border-border-subtle bg-surface-raised p-3 font-mono text-xs"
            placeholder="type,model,name,lang,source,value"
          />
        </section>

        <section className="mt-8 rounded-md border border-border-subtle bg-surface p-5">
          <h2 className="text-ui-title">
            ModuleSpec translations (CMP-11)
          </h2>
          <p className="mt-1 text-xs text-muted">
            {i18nProbe
              ? `Probe: ${i18nProbe.method} (Odoo ${i18nProbe.major ?? "?"}). ${i18nProbe.message}`
              : "Loading i18n probe…"}
          </p>
          <textarea
            value={specJson}
            onChange={(e) => setSpecJson(e.target.value)}
            rows={6}
            className="mt-3 w-full rounded-md border border-border-subtle bg-surface-raised p-3 font-mono text-xs"
            placeholder='{"models":[{"model":"x_lib_book","fields":[]}]}'
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const spec = JSON.parse(specJson) as Record<string, unknown>;
                  const csv = await api.exportSpecTranslationsCsv(connectionId, spec, lang);
                  setTranslationCsv(csv);
                  setNotice(`Exported app plan labels for ${lang}`);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Spec export failed");
                } finally {
                  setBusy(false);
                }
              }}
              className="border border-accent px-3 text-sm text-muted"
            >
              Export spec CSV
            </button>
            <button
              type="button"
              disabled={busy || !translationCsv}
              onClick={async () => {
                setBusy(true);
                try {
                  const res = await api.importSpecTranslations(connectionId, {
                    csv_text: translationCsv,
                    dry_run: true,
                  });
                  setNotice(
                    `Spec import test run: ${res.updated} would update, ${res.skipped} skipped`,
                  );
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Spec import failed");
                } finally {
                  setBusy(false);
                }
              }}
              className="border border-accent px-3 text-sm text-muted"
            >
              Spec import dry-run
            </button>
          </div>
        </section>
    </>
  );
}

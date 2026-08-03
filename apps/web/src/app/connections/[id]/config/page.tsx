"use client";

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, CompanyRow, Connection, SequenceRow } from "@/lib/api";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/layout-primitives";

const CONFIRM_PHRASE = "I understand the risks";

type CronRow = {
  id: number;
  name: string;
  model_name: string | null;
  interval_number: number | null;
  interval_type: string | null;
  active: boolean;
};

export default function ConfigPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [company, setCompany] = useState<CompanyRow | null>(null);
  const [sequences, setSequences] = useState<SequenceRow[]>([]);
  const [seqQuery, setSeqQuery] = useState("");
  const [mailTemplates, setMailTemplates] = useState<
    Array<{
      id: number;
      name: string;
      model: string | null;
      subject: string | null;
      email_to: string | null;
    }>
  >([]);
  const [activityTypes, setActivityTypes] = useState<
    Array<{ id: number; name: string; summary: string | null }>
  >([]);
  const [langs, setLangs] = useState<Array<{ code: string; name: string }>>([]);
  const [lang, setLang] = useState("en_US");
  const [labelModel, setLabelModel] = useState("res.partner");
  const [translationCsv, setTranslationCsv] = useState("");
  const [specJson, setSpecJson] = useState('{"models":[{"model":"x_demo","fields":[]}]}');
  const [i18nProbe, setI18nProbe] = useState<{
    ok: boolean;
    method: string;
    message: string;
    major: number | null;
  } | null>(null);
  const [mailForm, setMailForm] = useState({
    name: "",
    model: "res.partner",
    subject: "Hello ${object.name}",
    body_html: "<p>Hello,</p>",
    email_to: "${object.email}",
  });
  const [activityName, setActivityName] = useState("");
  const [seqForm, setSeqForm] = useState({
    name: "",
    code: "",
    prefix: "",
    padding: 5,
  });
  const [paperformats, setPaperformats] = useState<
    Array<{ id: number; name: string; format: string | null; margin_top: number | null }>
  >([]);
  const [paperForm, setPaperForm] = useState({ name: "", format: "A4", margin_top: 40 });
  const [defaults, setDefaults] = useState<
    Array<{ id: number; field_name: string | null; json_value: string | null }>
  >([]);
  const [defaultModel, setDefaultModel] = useState("res.partner");
  const [defaultField, setDefaultField] = useState("lang");
  const [defaultValue, setDefaultValue] = useState("");
  const [crons, setCrons] = useState<CronRow[]>([]);
  const [deactivateCron, setDeactivateCron] = useState<CronRow | null>(null);
  const [websiteNote, setWebsiteNote] = useState<string | null>(null);
  const [propertyNote, setPropertyNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [conn, cos, seqs, mails, acts, languages, papers, cronRows, sitePages, propsRes] =
      await Promise.all([
        api.getConnection(connectionId),
        api.listCompanies(connectionId),
        api.listSequences(connectionId, seqQuery || undefined),
        api.listConfigMailTemplates(connectionId),
        api.listConfigActivityTypes(connectionId),
        api.listLanguages(connectionId),
        api.listConfigPaperformats(connectionId),
        api.listIrCrons(connectionId),
        api.listWebsitePages(connectionId).catch(() => null),
        api.listIrProperties(connectionId).then(
          (rows) => ({ ok: true as const, rows }),
          (err: Error) => ({ ok: false as const, message: err.message }),
        ),
      ]);
    setConnection(conn);
    setCompanies(cos);
    setCompany((prev) => cos.find((c) => c.id === prev?.id) ?? cos[0] ?? null);
    setSequences(seqs);
    setMailTemplates(mails);
    setActivityTypes(acts);
    setLangs(languages);
    setPaperformats(papers);
    setCrons(cronRows);
    if (sitePages) {
      setWebsiteNote(
        sitePages.available
          ? `${sitePages.pages?.length ?? 0} website page(s)`
          : sitePages.reason || "website module not installed",
      );
    }
    if (propsRes.ok) {
      setPropertyNote(`${propsRes.rows.length} ir.property row(s)`);
    } else {
      setPropertyNote(propsRes.message);
    }
    if (languages[0] && !languages.some((l) => l.code === lang)) {
      setLang(languages[0].code);
    }
    const defs = await api.listIrDefaults(connectionId, defaultModel);
    setDefaults(defs);
    api.probeI18n(connectionId).then(setI18nProbe).catch(() => setI18nProbe(null));
  }, [connectionId, seqQuery, lang, defaultModel]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  async function saveCompany(e: FormEvent) {
    e.preventDefault();
    if (!company) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateCompany(connectionId, company.id, {
        name: company.name,
        email: company.email ?? undefined,
        phone: company.phone ?? undefined,
        website: company.website ?? undefined,
        street: company.street ?? undefined,
        street2: company.street2 ?? undefined,
        city: company.city ?? undefined,
        zip: company.zip ?? undefined,
        vat: company.vat ?? undefined,
        company_registry: company.company_registry ?? undefined,
      });
      setCompany(updated);
      setNotice(`Saved company #${updated.id}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl" data-testid="config-page">
      <PageHeader
        title="Settings"
        description="Company · sequences · mail · paperformat · defaults · cron · website"
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

        <form
          onSubmit={saveCompany}
          className="mt-8 space-y-3 border border-border-subtle bg-surface p-5 rounded-md"
        >
          <h2 className="font-[family-name:var(--font-display)] text-xl">Company</h2>
          {companies.length > 1 && (
            <select
              value={company?.id ?? ""}
              onChange={(e) =>
                setCompany(companies.find((c) => c.id === Number(e.target.value)) ?? null)
              }
              className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2 text-sm"
            >
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          {company && (
            <div className="grid gap-3 sm:grid-cols-2">
              {(
                [
                  ["name", "Name"],
                  ["email", "Email"],
                  ["phone", "Phone"],
                  ["website", "Website"],
                  ["street", "Street"],
                  ["street2", "Street 2"],
                  ["city", "City"],
                  ["zip", "ZIP"],
                  ["vat", "VAT"],
                  ["company_registry", "Company registry"],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="block text-sm">
                  <span className="text-muted">{label}</span>
                  <input
                    value={company[key] ?? ""}
                    onChange={(e) =>
                      setCompany({ ...company, [key]: e.target.value || null })
                    }
                    className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-3 py-2 text-sm"
                  />
                </label>
              ))}
            </div>
          )}
          <button
            type="submit"
            disabled={busy || !company}
            className="h-10 bg-accent px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            Save company
          </button>
        </form>

        <section className="mt-8 rounded-md border border-border-subtle bg-surface p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl">Sequences</h2>
          <form
            className="mt-3 flex flex-wrap gap-2"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await api.createSequence(connectionId, {
                  name: seqForm.name,
                  code: seqForm.code || null,
                  prefix: seqForm.prefix || null,
                  padding: seqForm.padding,
                });
                setSeqForm({ name: "", code: "", prefix: "", padding: 5 });
                setNotice("Sequence created");
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
              placeholder="Name"
              value={seqForm.name}
              onChange={(e) => setSeqForm({ ...seqForm, name: e.target.value })}
              className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1 text-sm"
            />
            <input
              placeholder="code"
              value={seqForm.code}
              onChange={(e) => setSeqForm({ ...seqForm, code: e.target.value })}
              className="w-28 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-sm"
            />
            <input
              placeholder="prefix"
              value={seqForm.prefix}
              onChange={(e) => setSeqForm({ ...seqForm, prefix: e.target.value })}
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
          <div className="mt-3 flex gap-2">
            <input
              value={seqQuery}
              onChange={(e) => setSeqQuery(e.target.value)}
              placeholder="Filter"
              className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => void refresh()}
              className="border border-border-subtle px-3 text-sm"
            >
              Refresh
            </button>
          </div>
          <ul className="mt-4 max-h-64 space-y-2 overflow-auto text-sm">
            {sequences.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-2 border-t border-border-subtle py-2">
                <span className="font-medium">
                  {s.name}{" "}
                  <span className="font-mono text-xs text-muted">{s.code}</span>
                </span>
                <input
                  value={s.prefix ?? ""}
                  onChange={(e) =>
                    setSequences((rows) =>
                      rows.map((r) =>
                        r.id === s.id ? { ...r, prefix: e.target.value } : r,
                      ),
                    )
                  }
                  className="w-24 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-xs"
                />
                <input
                  type="number"
                  value={s.number_next}
                  onChange={(e) =>
                    setSequences((rows) =>
                      rows.map((r) =>
                        r.id === s.id
                          ? { ...r, number_next: Number(e.target.value) }
                          : r,
                      ),
                    )
                  }
                  className="w-20 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-xs"
                />
                <button
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await api.updateSequence(connectionId, s.id, {
                        prefix: s.prefix ?? undefined,
                        number_next: s.number_next,
                        padding: s.padding,
                        active: s.active,
                      });
                      setNotice(`Updated sequence #${s.id}`);
                    } catch (err) {
                      setError(err instanceof Error ? err.message : "Update failed");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="text-xs text-muted"
                >
                  Save
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="rounded-md border border-border-subtle bg-surface p-5">
            <h2 className="font-[family-name:var(--font-display)] text-xl">Mail templates</h2>
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
            <h2 className="font-[family-name:var(--font-display)] text-xl">Activity types</h2>
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
            <h2 className="font-[family-name:var(--font-display)] text-xl">Paperformats</h2>
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
            <h2 className="font-[family-name:var(--font-display)] text-xl">Field defaults</h2>
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

        <section className="mt-8 rounded-md border border-border-subtle bg-surface p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl">Scheduled actions</h2>
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
          <h2 className="font-[family-name:var(--font-display)] text-xl">
            Website &amp; properties
          </h2>
          <p className="mt-2 text-sm text-muted">
            Website: {websiteNote ?? "—"}
          </p>
          <p className="mt-1 text-sm text-muted">
            ir.property: {propertyNote ?? "—"}
          </p>
        </section>

        <section className="mt-8 rounded-md border border-border-subtle bg-surface p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl">
            Translations CSV
          </h2>
          <p className="mt-1 text-xs text-muted">
            Lang-scoped field labels + root menu names (Odoo 19 context lang=). Confirm phrase
            not required for label writes — still prefer sandbox first.
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
              Dry-run
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
          <h2 className="font-[family-name:var(--font-display)] text-xl">
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
                  setNotice(`Exported ModuleSpec labels for ${lang}`);
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
                    `Spec import dry-run: ${res.updated} would update, ${res.skipped} skipped`,
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
      <ConfirmDialogV2
        open={deactivateCron != null}
        riskLevel="danger"
        title="Deactivate scheduled action"
        warning={
          deactivateCron
            ? `Stop ir.cron #${deactivateCron.id} (${deactivateCron.name}) on the live database.`
            : ""
        }
        risks={[
          "Background jobs stop until re-enabled",
          "Dependent processes may stall",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setDeactivateCron(null)}
        onConfirm={(phrase) => {
          if (!deactivateCron) return;
          void (async () => {
            setBusy(true);
            try {
              await api.patchIrCronActive(connectionId, deactivateCron.id, {
                active: false,
                confirm_advanced: true,
                confirm_phrase: phrase,
              });
              setNotice(`Deactivated cron #${deactivateCron.id}`);
              setDeactivateCron(null);
              await refresh();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Deactivate failed");
            } finally {
              setBusy(false);
            }
          })();
        }}
      />
    </div>
  );
}

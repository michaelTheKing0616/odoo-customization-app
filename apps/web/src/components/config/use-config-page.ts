"use client";

import { useCallback, useEffect, useState } from "react";
import { api, CompanyRow, Connection, SequenceRow } from "@/lib/api";
import type {
  ActivityTypeRow,
  CronRow,
  I18nProbe,
  IrDefaultRow,
  MailForm,
  MailHealth,
  MailTemplateRow,
  PaperForm,
  PaperformatRow,
  SeqForm,
} from "./config-types";

export function useConfigPage(connectionId: string) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [company, setCompany] = useState<CompanyRow | null>(null);
  const [sequences, setSequences] = useState<SequenceRow[]>([]);
  const [seqQuery, setSeqQuery] = useState("");
  const [mailTemplates, setMailTemplates] = useState<MailTemplateRow[]>([]);
  const [activityTypes, setActivityTypes] = useState<ActivityTypeRow[]>([]);
  const [langs, setLangs] = useState<Array<{ code: string; name: string }>>([]);
  const [lang, setLang] = useState("en_US");
  const [labelModel, setLabelModel] = useState("res.partner");
  const [translationCsv, setTranslationCsv] = useState("");
  const [specJson, setSpecJson] = useState('{"models":[{"model":"x_demo","fields":[]}]}');
  const [i18nProbe, setI18nProbe] = useState<I18nProbe | null>(null);
  const [mailForm, setMailForm] = useState<MailForm>({
    name: "",
    model: "res.partner",
    subject: "Hello ${object.name}",
    body_html: "<p>Hello,</p>",
    email_to: "${object.email}",
  });
  const [activityName, setActivityName] = useState("");
  const [seqForm, setSeqForm] = useState<SeqForm>({
    name: "",
    code: "",
    prefix: "",
    padding: 5,
  });
  const [paperformats, setPaperformats] = useState<PaperformatRow[]>([]);
  const [paperForm, setPaperForm] = useState<PaperForm>({ name: "", format: "A4", margin_top: 40 });
  const [defaults, setDefaults] = useState<IrDefaultRow[]>([]);
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
  const [listsHydrated, setListsHydrated] = useState(false);
  const [mailHealth, setMailHealth] = useState<MailHealth | null>(null);

  const refresh = useCallback(async () => {
    setListsHydrated(false);
    try {
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
    api
      .jobAutopilotFingerprint(connectionId)
      .then((out) => setMailHealth(out.fingerprint.mail ?? null))
      .catch(() => setMailHealth(null));
    } finally {
      setListsHydrated(true);
    }
  }, [connectionId, seqQuery, lang, defaultModel]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  return {
    connectionId,
    connection,
    companies,
    company,
    setCompany,
    sequences,
    setSequences,
    seqQuery,
    setSeqQuery,
    mailTemplates,
    activityTypes,
    langs,
    lang,
    setLang,
    labelModel,
    setLabelModel,
    translationCsv,
    setTranslationCsv,
    specJson,
    setSpecJson,
    i18nProbe,
    mailForm,
    setMailForm,
    activityName,
    setActivityName,
    seqForm,
    setSeqForm,
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
    crons,
    deactivateCron,
    setDeactivateCron,
    websiteNote,
    propertyNote,
    error,
    setError,
    notice,
    setNotice,
    busy,
    setBusy,
    listsHydrated,
    mailHealth,
    refresh,
  };
}

export type ConfigPageModel = ReturnType<typeof useConfigPage>;

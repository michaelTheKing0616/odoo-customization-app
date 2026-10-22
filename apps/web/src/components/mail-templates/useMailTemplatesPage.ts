"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, type Connection, type FieldRow } from "@/lib/api";
import {
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";
import {
  compileMailBodyBlocks,
  defaultMailBlocks,
  tryParseMailBodyBlocks,
  type MailBodyBlock,
} from "./mailBodyBlocks";
import { refuseUnsafeMailTemplate } from "./mailUnsafeGate";
import type { MailTemplatesCreateFormValues } from "./MailTemplatesCreateForm";
import type { MailTemplateListRow } from "./MailTemplatesListPanel";

const MAIL_CAVEAT =
  "Mail templates need the mail module. Placeholders render when Odoo sends — this studio does not claim ChatGPT-style freeform HTML when the unsafe gate refuses.";

export function useMailTemplatesPage(connectionId: string) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [templates, setTemplates] = useState<MailTemplateListRow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [subject, setSubject] = useState("");
  const [emailTo, setEmailTo] = useState("");
  const [bodyHtml, setBodyHtml] = useState("");
  const [blocks, setBlocks] = useState<MailBodyBlock[]>([]);
  const [editorTab, setEditorTab] = useState<"visual" | "source">("visual");
  const [fields, setFields] = useState<FieldRow[]>([]);
  const [fieldsLoading, setFieldsLoading] = useState(false);
  const [form, setForm] = useState<MailTemplatesCreateFormValues>({
    name: "Customer notice",
    model: "res.partner",
    subject: "Hello {{ object.name }}",
    email_to:
      "{{ object.email or (object.partner_id.email if object.partner_id else '') }}",
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listHydrated, setListHydrated] = useState(false);

  const refresh = useCallback(async () => {
    const rows = await api.listConfigMailTemplates(connectionId);
    setTemplates(rows);
  }, [connectionId]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  useEffect(() => {
    setListHydrated(false);
    refresh()
      .catch((err: Error) => setError(err.message))
      .finally(() => setListHydrated(true));
  }, [refresh]);

  const selected = templates.find((t) => t.id === selectedId) ?? null;

  useEffect(() => {
    if (!selected) {
      setSubject("");
      setEmailTo("");
      setBodyHtml("");
      setBlocks([]);
      return;
    }
    setSubject(selected.subject || "");
    setEmailTo(selected.email_to || "");
    const html = selected.body_html || "";
    setBodyHtml(html);
    const parsed = tryParseMailBodyBlocks(html);
    if (parsed) {
      setBlocks(parsed);
      setEditorTab("visual");
    } else {
      setBlocks([]);
      setEditorTab("source");
    }
  }, [selected]);

  useEffect(() => {
    const model = selected?.model || form.model;
    if (!model) {
      setFields([]);
      return;
    }
    let cancelled = false;
    setFieldsLoading(true);
    api
      .listFields(connectionId, model)
      .then((rows) => {
        if (!cancelled) setFields(rows);
      })
      .catch(() => {
        if (!cancelled) setFields([]);
      })
      .finally(() => {
        if (!cancelled) setFieldsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, selected?.model, form.model]);

  const canMutate = mutationAllowed(connection);
  const mutateBlocked = mutationBlockedReason(connection);
  const knownFields = useMemo(() => new Set(fields.map((f) => f.name)), [fields]);

  function formatError(msg: string) {
    return msg;
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const starter = defaultMailBlocks(form.name);
      const body_html = compileMailBodyBlocks(starter);
      const gate = refuseUnsafeMailTemplate({
        subject: form.subject,
        body_html,
        knownFields: fields.length ? knownFields : null,
      });
      if (gate) {
        setError(gate);
        return;
      }
      const created = await api.createConfigMailTemplate(connectionId, {
        name: form.name,
        model: form.model,
        subject: form.subject,
        body_html,
        email_to: form.email_to,
      });
      setNotice(`Created mail template #${created.id} on ${form.model}`);
      await refresh();
      setSelectedId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSave() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const html =
        editorTab === "visual" ? compileMailBodyBlocks(blocks) : bodyHtml;
      const gate = refuseUnsafeMailTemplate({
        subject,
        body_html: html,
        knownFields: fields.length ? knownFields : null,
      });
      if (gate) {
        setError(gate);
        return;
      }
      await api.updateConfigMailTemplate(connectionId, selectedId, {
        subject,
        body_html: html,
        email_to: emailTo,
      });
      setBodyHtml(html);
      setNotice(`Saved mail template #${selectedId}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return {
    connection,
    templates,
    selectedId,
    setSelectedId,
    selected,
    subject,
    setSubject,
    emailTo,
    setEmailTo,
    bodyHtml,
    setBodyHtml,
    blocks,
    setBlocks,
    editorTab,
    setEditorTab,
    fields,
    fieldsLoading,
    form,
    setForm,
    error,
    setError,
    notice,
    setNotice,
    busy,
    listHydrated,
    canMutate,
    mutateBlocked,
    mailCaveat: MAIL_CAVEAT,
    onCreate,
    onSave,
    formatError,
  };
}

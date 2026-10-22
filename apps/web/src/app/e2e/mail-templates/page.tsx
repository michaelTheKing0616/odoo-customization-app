"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";
import { MailTemplatesCreateForm } from "@/components/mail-templates/MailTemplatesCreateForm";
import { MailTemplatesListPanel, type MailTemplateListRow } from "@/components/mail-templates/MailTemplatesListPanel";
import { MailPaperPreview } from "@/components/mail-templates/MailPaperPreview";
import { compileMailBodyBlocks, defaultMailBlocks } from "@/components/mail-templates/mailBodyBlocks";
import styles from "@/components/mail-templates/MailTemplatesPage.module.css";

/**
 * DOC-MAIL vision harness — paper desk + list chrome. Gated by NEXT_PUBLIC_E2E.
 */
type Shot = "desktop" | "empty" | "preview";

const FIXTURES: MailTemplateListRow[] = [
  {
    id: 21,
    name: "Delivery note",
    model: "x_delivery.order",
    subject: "Delivery {{ object.name }}",
    body_html: compileMailBodyBlocks(defaultMailBlocks("Delivery note")),
    email_to: "{{ object.partner_id.email }}",
  },
  {
    id: 22,
    name: "Partner hello",
    model: "res.partner",
    subject: "Hello {{ object.name }}",
    body_html: "<p>Welcome {{ object.name }}</p>",
    email_to: "{{ object.email }}",
  },
];

export default function MailTemplatesHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [shot, setShot] = useState<Shot>("desktop");
  const [selectedId, setSelectedId] = useState<number | null>(21);
  const [form, setForm] = useState({
    name: "Customer notice",
    model: "res.partner",
    subject: "Hello {{ object.name }}",
    email_to: "{{ object.email }}",
  });

  const templates = useMemo(
    () => (shot === "empty" ? [] : FIXTURES),
    [shot],
  );
  const selected = templates.find((t) => t.id === selectedId) ?? FIXTURES[0];

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main className={`${styles.page} mx-auto max-w-5xl p-6`} data-testid="mail-templates-e2e">
      <PageHeader
        title="Mail templates (vision)"
        description="DOC-MAIL harness — pasteboard paper letter, not a raw textarea."
      />
      <div className="mt-4 flex flex-wrap gap-2">
        {(["desktop", "empty", "preview"] as Shot[]).map((s) => (
          <Button
            key={s}
            type="button"
            size="sm"
            variant={shot === s ? "primary" : "secondary"}
            onClick={() => setShot(s)}
            data-testid={`shot-${s}`}
          >
            {s}
          </Button>
        ))}
      </div>

      <div className="mt-6 space-y-5">
        <MailTemplatesCreateForm
          form={form}
          onChange={setForm}
          onSubmit={(e) => e.preventDefault()}
        />
        {shot === "preview" ? (
          <MailPaperPreview
            subject={selected.subject || ""}
            emailTo={selected.email_to}
            bodyHtml={selected.body_html || ""}
          />
        ) : (
          <div className={styles.workbench} data-testid="mail-templates-workbench">
            <MailTemplatesListPanel
              templates={templates}
              selectedId={selectedId}
              hydrated
              onSelect={setSelectedId}
              embedded
            />
            <div className={styles.editorPane}>
              <div className={styles.editorBody}>
                <MailPaperPreview
                  subject={selected?.subject || "Select a template"}
                  emailTo={selected?.email_to}
                  bodyHtml={selected?.body_html || "<p></p>"}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

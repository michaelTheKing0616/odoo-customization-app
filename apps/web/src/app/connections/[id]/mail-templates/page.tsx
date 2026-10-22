"use client";

import { useParams } from "next/navigation";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/layout-primitives";
import { MailTemplatesCreateForm } from "@/components/mail-templates/MailTemplatesCreateForm";
import { MailTemplatesEditor } from "@/components/mail-templates/MailTemplatesEditor";
import { MailTemplatesListPanel } from "@/components/mail-templates/MailTemplatesListPanel";
import { useMailTemplatesPage } from "@/components/mail-templates/useMailTemplatesPage";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import styles from "@/components/mail-templates/MailTemplatesPage.module.css";

/** DOC-MAIL — mail.template studio on the paper desk (Canva pasteboard family). */
export default function MailTemplatesPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const s = useMailTemplatesPage(connectionId);

  return (
    <div className={`${styles.page} mx-auto max-w-5xl`} data-testid="mail-templates-page">
      <PageHeader
        title="Mail templates"
        description="Design email letters for a record type on a paper canvas. Only real fields, with the same safety checks as PDF reports."
      />
      <VersionAwarenessBanner
        capabilities={s.connection?.capabilities}
        caveat={s.mailCaveat}
      />
      {s.mutateBlocked ? (
        <Callout variant="warning" title="Changes are switched off" className="mt-4">
          {s.mutateBlocked}
        </Callout>
      ) : null}
      {s.error ? <ErrorNotice message={s.error} className="mt-4" /> : null}
      {s.notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {s.notice}
        </Callout>
      ) : null}

      <div className="mt-8 space-y-5">
        <MailTemplatesCreateForm
          form={s.form}
          busy={s.busy}
          canSubmit={s.canMutate}
          submitBlockedReason={s.mutateBlocked}
          onChange={s.setForm}
          onSubmit={s.onCreate}
        />

        <div className={styles.workbench} data-testid="mail-templates-workbench">
          <MailTemplatesListPanel
            templates={s.templates}
            selectedId={s.selectedId}
            hydrated={s.listHydrated}
            onSelect={s.setSelectedId}
            embedded
          />
          <MailTemplatesEditor
            template={s.selected}
            subject={s.subject}
            emailTo={s.emailTo}
            bodyHtml={s.bodyHtml}
            blocks={s.blocks}
            fields={s.fields}
            fieldsLoading={s.fieldsLoading}
            editorTab={s.editorTab}
            busy={s.busy}
            canMutate={s.canMutate}
            mutateBlocked={s.mutateBlocked}
            onSubjectChange={s.setSubject}
            onEmailToChange={s.setEmailTo}
            onBodyHtmlChange={s.setBodyHtml}
            onBlocksChange={s.setBlocks}
            onEditorTabChange={s.setEditorTab}
            onSave={s.onSave}
            onError={(msg) => s.setError(s.formatError(msg))}
          />
        </div>
      </div>
    </div>
  );
}

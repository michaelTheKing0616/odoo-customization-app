"use client";

import { useParams } from "next/navigation";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/layout-primitives";
import { QwebViewsCreateForm } from "@/components/qweb-views/QwebViewsCreateForm";
import { QwebViewsEditor } from "@/components/qweb-views/QwebViewsEditor";
import { QwebViewsListPanel } from "@/components/qweb-views/QwebViewsListPanel";
import { useQwebViewsPage } from "@/components/qweb-views/useQwebViewsPage";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import styles from "@/components/qweb-views/QwebViewsPage.module.css";

/** DOC-QWEB — general ir.ui.view type=qweb on the paper desk. */
export default function QwebViewsPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const s = useQwebViewsPage(connectionId);

  return (
    <div className={`${styles.page} mx-auto max-w-5xl`} data-testid="qweb-views-page">
      <PageHeader
        title="QWeb views"
        description="Edit general type=qweb arches on a paper canvas — grounded blocks where possible, Source XML for foreign bodies, the same safety checks as Reports."
      />
      <VersionAwarenessBanner
        capabilities={s.connection?.capabilities}
        caveat={s.qwebCaveat}
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
        <QwebViewsCreateForm
          form={s.form}
          busy={s.busy}
          canSubmit={s.canMutate}
          submitBlockedReason={s.mutateBlocked}
          onChange={s.setForm}
          onSubmit={s.onCreate}
        />

        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={s.excludeReportBound}
            onChange={(e) => s.setExcludeReportBound(e.target.checked)}
            data-testid="qweb-exclude-reports"
          />
          Hide views already bound to ir.actions.report (use Reports studio for those)
        </label>

        <div className={styles.workbench} data-testid="qweb-views-workbench">
          <QwebViewsListPanel
            views={s.views}
            selectedId={s.selectedId}
            hydrated={s.listHydrated}
            onSelect={s.setSelectedId}
            embedded
          />
          <QwebViewsEditor
            view={s.detail}
            arch={s.arch}
            blocks={s.blocks}
            fields={s.fields}
            fieldsLoading={s.fieldsLoading}
            editorTab={s.editorTab}
            strategy={s.strategy}
            inheritXpath={s.inheritXpath}
            inheritPosition={s.inheritPosition}
            existingTCalls={s.existingTCalls}
            busy={s.busy}
            canMutate={s.canMutate}
            mutateBlocked={s.mutateBlocked}
            onArchChange={s.setArch}
            onBlocksChange={s.setBlocks}
            onEditorTabChange={s.setEditorTab}
            onStrategyChange={s.setStrategy}
            onInheritXpathChange={s.setInheritXpath}
            onInheritPositionChange={s.setInheritPosition}
            onSave={s.onSave}
            onError={(msg) => s.setError(s.formatError(msg))}
          />
        </div>
      </div>
    </div>
  );
}

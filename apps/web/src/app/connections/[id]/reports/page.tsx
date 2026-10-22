"use client";

import { useParams } from "next/navigation";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/layout-primitives";
import { ReportsCombinedPrint } from "@/components/reports/ReportsCombinedPrint";
import { ReportsCreateForm } from "@/components/reports/ReportsCreateForm";
import { ReportsDeleteConfirm } from "@/components/reports/ReportsDeleteConfirm";
import { ReportsEditorPanel } from "@/components/reports/ReportsEditorPanel";
import { ReportsListPanel } from "@/components/reports/ReportsListPanel";
import { useReportsPage } from "@/components/reports/useReportsPage";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import styles from "@/components/reports/ReportsPage.module.css";

/** PDF-06 / UI-S-17 — desk chrome around the A4 paper canvas (Canva/Affinity / Linear). */
export default function ReportsPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const s = useReportsPage(connectionId);

  return (
    <div className={`${styles.page} mx-auto max-w-5xl`} data-testid="reports-page">
      <PageHeader
        title="Report layout lite"
        description="Design QWeb PDF printouts on a paper canvas — create from scratch or extend one stock slot."
      />
      <VersionAwarenessBanner
        capabilities={s.connection?.capabilities}
        caveat={s.reportsCaveat}
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
        <ReportsCreateForm
          form={s.form}
          papers={s.papers}
          busy={s.busy}
          canSubmit={s.canMutate}
          submitBlockedReason={s.mutateBlocked}
          onChange={s.setForm}
          onSubmit={s.onCreate}
        />

        <div className={styles.workbench} data-testid="reports-workbench">
          <ReportsListPanel
            reports={s.reports}
            selectedId={s.selectedId}
            hydrated={s.listHydrated}
            onSelect={s.setSelectedId}
            embedded
          />
          <ReportsEditorPanel
            connectionId={connectionId}
            connection={s.connection}
            reports={s.reports}
            selectedId={s.selectedId}
            selectedReport={s.selectedReport}
            formModel={s.form.model}
            formReportKey={s.form.report_key}
            formName={s.form.name}
            arch={s.arch}
            editorTab={s.editorTab}
            busy={s.busy}
            canMutate={s.canMutate}
            canAdvanced={s.canAdvanced}
            mutateBlocked={s.mutateBlocked}
            advancedBlocked={s.advancedBlocked}
            lastInheritOp={s.lastInheritOp}
            onEditorTabChange={s.setEditorTab}
            onArchChange={s.setArch}
            onInheritOpChange={s.setLastInheritOp}
            embedded
            onEmitSave={async ({ arch, op }) => {
              await s.persistArch(arch, op);
            }}
            onSaveArch={async () => {
              if (!s.selectedId) return;
              try {
                await s.persistArch(s.arch, s.lastInheritOp);
              } catch {
                /* surfaced via error state */
              }
            }}
            onApplyToProduction={() =>
              s.setNotice(
                "Apply to production stays a human promote step after sandbox render.",
              )
            }
            onDelete={() => s.setConfirmDelete(true)}
            onNotice={s.setNotice}
            onError={(msg) => s.setError(s.formatError(msg))}
          />
        </div>

        <ReportsCombinedPrint
          reports={s.reports}
          mergeRows={s.mergeRows}
          busy={s.busy}
          renderProbe={s.renderProbe}
          onChangeRows={s.setMergeRows}
          onProbe={() => void s.probeRenderPath()}
          onDownload={() => void s.downloadMergedPdf()}
        />
      </div>

      <ReportsDeleteConfirm
        open={s.confirmDelete}
        busy={s.busy}
        onCancel={() => s.setConfirmDelete(false)}
        onConfirm={s.onDeleteConfirm}
      />
    </div>
  );
}

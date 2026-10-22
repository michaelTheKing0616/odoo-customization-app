"use client";

import type { Connection } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { ReportDesigner } from "@/components/reports/ReportDesigner";
import type { ReportInheritOp } from "@/components/reports/reportInheritSlots";
import type { ReportListRow } from "@/components/reports/ReportsListPanel";
import { cn } from "@/lib/cn";
import styles from "./ReportsPage.module.css";

type ReportsEditorPanelProps = {
  connectionId: string;
  connection: Connection | null;
  reports: ReportListRow[];
  selectedId: number | null;
  selectedReport: ReportListRow | null;
  formModel: string;
  formReportKey: string;
  formName: string;
  arch: string;
  editorTab: "visual" | "code";
  busy: boolean;
  canMutate: boolean;
  canAdvanced: boolean;
  mutateBlocked: string | null;
  advancedBlocked: string | null;
  lastInheritOp: ReportInheritOp | null;
  onEditorTabChange: (tab: "visual" | "code") => void;
  onArchChange: (arch: string) => void;
  onInheritOpChange: (op: ReportInheritOp | null) => void;
  onEmitSave: (payload: {
    arch: string;
    op: ReportInheritOp | null;
  }) => void | Promise<void>;
  onSaveArch: () => void | Promise<void>;
  onApplyToProduction: () => void;
  onDelete: () => void;
  onNotice: (msg: string) => void;
  onError: (msg: string) => void;
  /** When true, omit outer border (workbench provides shell). */
  embedded?: boolean;
};

/**
 * PDF-06 — Framer/Linear operate chrome around ReportDesigner.
 * Primary action label: "Save the printout". Underline tabs; desk body for paper.
 */
export function ReportsEditorPanel({
  connectionId,
  connection,
  reports,
  selectedId,
  selectedReport,
  formModel,
  formReportKey,
  formName,
  arch,
  editorTab,
  busy,
  canMutate,
  canAdvanced,
  mutateBlocked,
  advancedBlocked,
  lastInheritOp,
  onEditorTabChange,
  onArchChange,
  onInheritOpChange,
  onEmitSave,
  onSaveArch,
  onApplyToProduction,
  onDelete,
  onNotice,
  onError,
  embedded = false,
}: ReportsEditorPanelProps) {
  return (
    <div
      className={cn(styles.editorPane, !embedded && "rounded-[12px] border border-[color:var(--reports-hairline,rgba(0,0,0,.1))] overflow-hidden")}
      data-testid="reports-editor-panel"
    >
      <div className={styles.editorToolbar}>
        <div className={styles.tabs} role="tablist" aria-label="Report editor">
          {(
            [
              ["visual", "Visual"],
              ["code", "QWeb"],
            ] as const
          ).map(([id, label]) => {
            const active = editorTab === id;
            return (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => onEditorTabChange(id)}
                className={cn(styles.tab, active && styles.tabActive)}
              >
                {label}
              </button>
            );
          })}
        </div>
        <Button
          type="button"
          variant="primary"
          size="sm"
          disabled={busy || !selectedId || !canMutate}
          title={mutateBlocked ?? undefined}
          data-testid="reports-save-arch"
          onClick={() => void onSaveArch()}
        >
          Save the printout
        </Button>
      </div>

      <div className={styles.editorBody}>
        {editorTab === "visual" ? (
          !selectedId ? (
            <p className="px-2 py-8 text-center text-sm text-muted">
              Create or select a printout — the A4 sheet opens on this desk.
            </p>
          ) : (
            <ReportDesigner
              connectionId={connectionId}
              model={selectedReport?.model || formModel}
              reportKey={selectedReport?.report_name || formReportKey}
              reportName={selectedReport?.name || formName}
              reportId={selectedId}
              paperLabel={selectedReport?.paperformat_name || "A4"}
              connection={connection}
              availableReports={reports}
              initialArch={selectedReport?.arch || arch}
              onArchChange={onArchChange}
              onInheritOpChange={onInheritOpChange}
              onEmitSave={async ({ arch: nextArch, op }) => {
                await onEmitSave({ arch: nextArch, op });
              }}
              onNotice={onNotice}
              onError={onError}
            />
          )
        ) : (
          <>
            <p className="text-xs font-medium text-muted">QWeb arch</p>
            <textarea
              value={arch}
              onChange={(e) => onArchChange(e.target.value)}
              rows={16}
              disabled={!selectedId}
              spellCheck={false}
              className={styles.codeArea}
            />
          </>
        )}
      </div>

      <div className={styles.editorFooter}>
        {canAdvanced ? (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={busy || !selectedId}
            data-testid="reports-apply-to-production"
            title={advancedBlocked ?? "Sandbox-render before production apply"}
            onClick={onApplyToProduction}
          >
            Apply to production
          </Button>
        ) : null}
        <Button
          type="button"
          variant="danger"
          size="sm"
          disabled={busy || !selectedId || !canAdvanced}
          title={advancedBlocked ?? undefined}
          onClick={onDelete}
        >
          Delete
        </Button>
        {lastInheritOp ? (
          <span className={styles.inheritChip} data-testid="reports-inherit-op-chip">
            inherit · {lastInheritOp.params.xpath}
          </span>
        ) : null}
      </div>
    </div>
  );
}

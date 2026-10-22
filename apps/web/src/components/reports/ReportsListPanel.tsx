"use client";

import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { cn } from "@/lib/cn";
import styles from "./ReportsPage.module.css";

export type ReportListRow = {
  id: number;
  name: string;
  model: string | null;
  report_name: string | null;
  paperformat_name?: string | null;
  arch?: string | null;
};

type ReportsListPanelProps = {
  reports: ReportListRow[];
  selectedId: number | null;
  hydrated: boolean;
  onSelect: (id: number) => void;
  /** When true, omit the outer pane shell (workbench already provides it). */
  embedded?: boolean;
};

/**
 * PDF-06 / UI-F03 — Linear-style printout list on the desk.
 * Kit Skeleton + EmptyState. Active row: left accent hairline, not a card ring.
 */
export function ReportsListPanel({
  reports,
  selectedId,
  hydrated,
  onSelect,
  embedded = false,
}: ReportsListPanelProps) {
  const body = (
    <>
      <div className={styles.listHead}>
        <p className={styles.listHeadLabel}>Printouts</p>
        <p className={styles.listHeadMeta}>
          {hydrated ? `${reports.length} on this connection` : "Reading reports from Odoo…"}
        </p>
      </div>
      <div className={styles.listBody}>
        {!hydrated ? (
          <div className="space-y-2 p-1" data-testid="reports-list-loading">
            <Skeleton className="h-11 w-full rounded-lg" />
            <Skeleton className="h-11 w-full rounded-lg" />
            <Skeleton className="h-11 w-full rounded-lg" />
          </div>
        ) : reports.length === 0 ? (
          <div className={styles.emptyDesk}>
            <EmptyState
              title="No custom reports yet"
              description="Start with New printout — the sheet opens on this desk."
              action={
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    document
                      .getElementById("reports-create-form")
                      ?.scrollIntoView({ behavior: "smooth" })
                  }
                >
                  Open create form
                </Button>
              }
            />
          </div>
        ) : (
          <ul className="space-y-0.5" role="listbox" aria-label="Reports">
            {reports.map((r) => {
              const active = selectedId === r.id;
              return (
                <li key={r.id} role="option" aria-selected={active}>
                  <button
                    type="button"
                    onClick={() => onSelect(r.id)}
                    className={cn(
                      styles.listRow,
                      active && styles.listRowActive,
                    )}
                  >
                    <span className={styles.listRowTitle}>{r.name}</span>
                    <span className={styles.listRowMeta}>
                      {r.model} · {r.report_name}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </>
  );

  if (embedded) {
    return (
      <div className={styles.listPane} data-testid="reports-list">
        {body}
      </div>
    );
  }

  return (
    <div
      className={cn(styles.listPane, "rounded-[12px] border border-[color:var(--reports-hairline,rgba(0,0,0,.1))]")}
      data-testid="reports-list"
      style={{ ["--reports-desk" as string]: "var(--n2, #f4f4f5)" }}
    >
      {body}
    </div>
  );
}

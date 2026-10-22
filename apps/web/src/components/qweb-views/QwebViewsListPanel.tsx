"use client";

import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { cn } from "@/lib/cn";
import styles from "./QwebViewsPage.module.css";

export type QwebViewListRow = {
  id: number;
  name: string;
  key: string | null;
  model: string | null;
  inherit_id?: number | null;
  inherit_name?: string | null;
  mode?: string | null;
  priority?: number | null;
  report_bound?: boolean;
  report_name?: string | null;
};

type Props = {
  views: QwebViewListRow[];
  selectedId: number | null;
  hydrated: boolean;
  onSelect: (id: number) => void;
  embedded?: boolean;
};

export function QwebViewsListPanel({
  views,
  selectedId,
  hydrated,
  onSelect,
  embedded = false,
}: Props) {
  const body = (
    <>
      <div className={styles.listHead}>
        <p className={styles.listHeadLabel}>QWeb views</p>
        <p className={styles.listHeadMeta}>
          {hydrated ? `${views.length} on this connection` : "Reading report layouts from Odoo…"}
        </p>
      </div>
      <div className={styles.listBody}>
        {!hydrated ? (
          <div className="space-y-2 p-1" data-testid="qweb-views-list-loading">
            <Skeleton className="h-11 w-full rounded-lg" />
            <Skeleton className="h-11 w-full rounded-lg" />
            <Skeleton className="h-11 w-full rounded-lg" />
          </div>
        ) : views.length === 0 ? (
          <div className={styles.emptyDesk}>
            <EmptyState
              title="No general QWeb views yet"
              description="Create a keyed template, or open an existing type=qweb arch from this connection."
              action={
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    document
                      .getElementById("qweb-views-create-form")
                      ?.scrollIntoView({ behavior: "smooth" })
                  }
                >
                  Open create form
                </Button>
              }
            />
          </div>
        ) : (
          <ul className="space-y-0.5" role="listbox" aria-label="QWeb views">
            {views.map((v) => {
              const active = selectedId === v.id;
              return (
                <li key={v.id} role="option" aria-selected={active}>
                  <button
                    type="button"
                    onClick={() => onSelect(v.id)}
                    className={cn(styles.listRow, active && styles.listRowActive)}
                  >
                    <span className={styles.listRowTitle}>{v.name}</span>
                    <span className={styles.listRowMeta}>
                      {v.key || "no key"}
                      {v.report_bound ? " · report" : ""}
                      {v.inherit_id ? " · inherit" : ""}
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
      <div className={styles.listPane} data-testid="qweb-views-list">
        {body}
      </div>
    );
  }

  return (
    <div className={cn(styles.listPane, "rounded-[12px] border")} data-testid="qweb-views-list">
      {body}
    </div>
  );
}

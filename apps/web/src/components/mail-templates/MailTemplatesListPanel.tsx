"use client";

import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { cn } from "@/lib/cn";
import styles from "./MailTemplatesPage.module.css";

export type MailTemplateListRow = {
  id: number;
  name: string;
  model: string | null;
  subject: string | null;
  body_html?: string | null;
  email_to?: string | null;
  description?: string | null;
};

type Props = {
  templates: MailTemplateListRow[];
  selectedId: number | null;
  hydrated: boolean;
  onSelect: (id: number) => void;
  embedded?: boolean;
};

export function MailTemplatesListPanel({
  templates,
  selectedId,
  hydrated,
  onSelect,
  embedded = false,
}: Props) {
  const body = (
    <>
      <div className={styles.listHead}>
        <p className={styles.listHeadLabel}>Templates</p>
        <p className={styles.listHeadMeta}>
          {hydrated ? `${templates.length} on this connection` : "Reading email templates from Odoo…"}
        </p>
      </div>
      <div className={styles.listBody}>
        {!hydrated ? (
          <div className="space-y-2 p-1" data-testid="mail-templates-list-loading">
            <Skeleton className="h-11 w-full rounded-lg" />
            <Skeleton className="h-11 w-full rounded-lg" />
            <Skeleton className="h-11 w-full rounded-lg" />
          </div>
        ) : templates.length === 0 ? (
          <div className={styles.emptyDesk}>
            <EmptyState
              title="No mail templates yet"
              description="Create one bound to a real model — the letter opens on this desk."
              action={
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    document
                      .getElementById("mail-templates-create-form")
                      ?.scrollIntoView({ behavior: "smooth" })
                  }
                >
                  Open create form
                </Button>
              }
            />
          </div>
        ) : (
          <ul className="space-y-0.5" role="listbox" aria-label="Mail templates">
            {templates.map((t) => {
              const active = selectedId === t.id;
              return (
                <li key={t.id} role="option" aria-selected={active}>
                  <button
                    type="button"
                    onClick={() => onSelect(t.id)}
                    className={cn(styles.listRow, active && styles.listRowActive)}
                  >
                    <span className={styles.listRowTitle}>{t.name}</span>
                    <span className={styles.listRowMeta}>
                      {t.model || "—"} · {t.subject || "no subject"}
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
      <div className={styles.listPane} data-testid="mail-templates-list">
        {body}
      </div>
    );
  }

  return (
    <div className={cn(styles.listPane, "rounded-[12px] border")} data-testid="mail-templates-list">
      {body}
    </div>
  );
}

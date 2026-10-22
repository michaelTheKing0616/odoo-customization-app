"use client";

import type { ReactNode } from "react";
import { sanitizeQwebArchForPreview } from "./qwebUnsafeGate";
import styles from "./QwebViewsPage.module.css";

type Props = {
  title: string;
  keyLabel?: string | null;
  model?: string | null;
  bodyHtml: string;
  children?: ReactNode;
  testId?: string;
};

/**
 * QWeb-as-paper artifact on the pasteboard (Canva / Reports / Mail family).
 * Preview HTML is sanitized; save still goes through qwebUnsafeGate.
 */
export function QwebPaperPreview({
  title,
  keyLabel,
  model,
  bodyHtml,
  children,
  testId = "qweb-paper-preview",
}: Props) {
  const safe = sanitizeQwebArchForPreview(bodyHtml);

  return (
    <div className={styles.stage} data-testid={testId}>
      <article className={styles.paper} aria-label="QWeb paper preview">
        <header className={styles.paperHeader}>
          <p className={styles.paperMetaLabel}>QWeb view</p>
          <h3 className={styles.paperSubject}>{title || "Untitled view"}</h3>
          <p className={styles.paperTo} title={keyLabel || undefined}>
            {[keyLabel, model].filter(Boolean).join(" · ") || "no key"}
          </p>
        </header>
        <div className={styles.paperBody}>
          {children ? (
            children
          ) : (
            <div
              data-testid="qweb-paper-body"
              // Preview-only; gated on save via refuseUnsafeQwebViewArch.
              dangerouslySetInnerHTML={{
                __html: safe || "<p><em>Empty arch</em></p>",
              }}
            />
          )}
        </div>
      </article>
    </div>
  );
}

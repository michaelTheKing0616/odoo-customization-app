"use client";

import type { ReactNode } from "react";
import { sanitizeMailHtmlForPreview } from "./mailUnsafeGate";
import styles from "./MailTemplatesPage.module.css";

type Props = {
  subject: string;
  emailTo?: string | null;
  bodyHtml: string;
  /** When true, render editable block children instead of sanitized HTML. */
  children?: ReactNode;
  testId?: string;
};

/**
 * Email-as-paper artifact on the pasteboard (Canva family).
 * Preview HTML is sanitized; save still goes through mailUnsafeGate.
 */
export function MailPaperPreview({
  subject,
  emailTo,
  bodyHtml,
  children,
  testId = "mail-paper-preview",
}: Props) {
  const safe = sanitizeMailHtmlForPreview(bodyHtml);

  return (
    <div className={styles.stage} data-testid={testId}>
      <article className={styles.paper} aria-label="Email paper preview">
        <header className={styles.paperHeader}>
          <p className={styles.paperMetaLabel}>Subject</p>
          <h3 className={styles.paperSubject}>{subject || "Untitled subject"}</h3>
          {emailTo ? (
            <p className={styles.paperTo} title={emailTo}>
              To · {emailTo}
            </p>
          ) : null}
        </header>
        <div className={styles.paperBody}>
          {children ? (
            children
          ) : (
            <div
              data-testid="mail-paper-body"
              // Preview-only; gated on save via refuseUnsafeMailHtml.
              dangerouslySetInnerHTML={{ __html: safe || "<p><em>Empty body</em></p>" }}
            />
          )}
        </div>
      </article>
    </div>
  );
}

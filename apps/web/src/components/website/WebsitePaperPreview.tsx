"use client";

import type { WebsiteBlock } from "./WebsiteEditor";
import { sanitizeWebsiteHtmlForPreview } from "./websiteUnsafeGate";
import styles from "./WebsitePage.module.css";

type Props = {
  name: string;
  url?: string | null;
  blocks: WebsiteBlock[];
  testId?: string;
};

function renderBlockHtml(block: WebsiteBlock): string {
  if (block.kind === "locked") {
    return `<span class="site-locked" data-locked="1">Locked XML</span>`;
  }
  if (block.kind === "section") {
    const inner = (block.children || []).map(renderBlockHtml).join("");
    return `<section>${inner}</section>`;
  }
  if (block.kind === "heading") {
    const level = Math.min(Math.max(block.level || 2, 1), 6);
    return `<h${level}>${escapeText(block.text || "Heading")}</h${level}>`;
  }
  if (block.kind === "paragraph") {
    return `<p>${escapeText(block.text || "")}</p>`;
  }
  if (block.kind === "link") {
    return `<p><a href="${escapeAttr(block.href || "#")}">${escapeText(block.text || "Link")}</a></p>`;
  }
  if (block.kind === "button") {
    return `<p><a href="${escapeAttr(block.href || "#")}">${escapeText(block.text || "Button")}</a></p>`;
  }
  if (block.kind === "image") {
    if (!block.src) return `<p><em>Image</em></p>`;
    return `<p><img src="${escapeAttr(block.src)}" alt="" /></p>`;
  }
  return "";
}

function escapeText(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeAttr(text: string): string {
  return text.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/**
 * Website page as paper on the pasteboard (Canva family).
 * Preview HTML is sanitized; save still goes through websiteUnsafeGate.
 */
export function WebsitePaperPreview({
  name,
  url,
  blocks,
  testId = "website-paper-preview",
}: Props) {
  const raw = blocks.map(renderBlockHtml).join("") || "<p><em>Empty page</em></p>";
  const safe = sanitizeWebsiteHtmlForPreview(raw);

  return (
    <div className={styles.stage} data-testid={testId}>
      <article className={styles.paper} aria-label="Website page preview">
        <header className={styles.paperHeader}>
          <p className={styles.paperMetaLabel}>Page</p>
          <h3 className={styles.paperTitle}>{name || "Untitled page"}</h3>
          {url ? (
            <p className={styles.paperUrl} title={url}>
              {url}
            </p>
          ) : null}
        </header>
        <div
          className={styles.paperBody}
          data-testid="website-paper-body"
          // Preview-only; gated on save via refuseUnsafeWebsiteSave.
          dangerouslySetInnerHTML={{ __html: safe }}
        />
      </article>
    </div>
  );
}

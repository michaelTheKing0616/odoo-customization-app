"use client";

import { useCallback, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input } from "@/components/ui/Input";
import { ChevronDown, ChevronUp } from "@/components/ui/icons";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { WebsitePaperPreview } from "./WebsitePaperPreview";
import { formatWebsiteError, type WebsiteErrorParts } from "./websiteError";
import { refuseUnsafeWebsiteSave } from "./websiteUnsafeGate";
import styles from "./WebsitePage.module.css";

export type WebsiteBlock = {
  id: string;
  kind: string;
  text?: string;
  href?: string;
  src?: string;
  level?: number;
  locked_xml?: string;
  children?: WebsiteBlock[];
};

export type WebsitePageSummary = {
  id: number;
  name: string | null;
  url: string | null;
  is_published?: boolean | null;
};

type PageState = {
  pageId: number;
  viewId: number;
  name: string;
  url: string | null;
  isPublished: boolean;
  blocks: WebsiteBlock[];
};

type Props = {
  connectionId: string;
  pages: WebsitePageSummary[];
  pagesAvailable: boolean;
  unavailableReason?: string | null;
  pagesLoading?: boolean;
  onRefreshPages?: () => void;
  /** E2E harness: skip network load */
  initialState?: PageState;
  onSaved?: (note: string) => void;
};

function cloneBlocks(blocks: WebsiteBlock[]): WebsiteBlock[] {
  return blocks.map((b) => ({
    ...b,
    children: b.children ? cloneBlocks(b.children) : undefined,
  }));
}

function updateBlockTree(
  blocks: WebsiteBlock[],
  id: string,
  patch: Partial<WebsiteBlock>,
): WebsiteBlock[] {
  return blocks.map((b) => {
    if (b.id === id) return { ...b, ...patch };
    if (b.children?.length) {
      return { ...b, children: updateBlockTree(b.children, id, patch) };
    }
    return b;
  });
}

function reorderSibling(
  blocks: WebsiteBlock[],
  id: string,
  direction: "up" | "down",
): WebsiteBlock[] {
  const idx = blocks.findIndex((b) => b.id === id);
  if (idx >= 0) {
    const swap = direction === "up" ? idx - 1 : idx + 1;
    if (swap < 0 || swap >= blocks.length) return blocks;
    const next = [...blocks];
    [next[idx], next[swap]] = [next[swap], next[idx]];
    return next;
  }
  return blocks.map((b) =>
    b.children?.length
      ? { ...b, children: reorderSibling(b.children, id, direction) }
      : b,
  );
}

function countLocked(blocks: WebsiteBlock[]): number {
  let n = 0;
  for (const b of blocks) {
    if (b.kind === "locked") n += 1;
    if (b.children?.length) n += countLocked(b.children);
  }
  return n;
}

function WebsiteErrorCard({
  parts,
  onRetry,
}: {
  parts: WebsiteErrorParts;
  onRetry?: () => void;
}) {
  return (
    <div
      className={styles.errorCard}
      role="alert"
      data-testid="website-error"
    >
      <p className={styles.errorWhat} data-testid="website-error-what">
        {parts.what}
      </p>
      <div className={styles.errorRow}>
        <p className={styles.errorLabel}>Why</p>
        <p className={styles.errorText} data-testid="website-error-why">
          {parts.why}
        </p>
      </div>
      <div className={styles.errorRow}>
        <p className={styles.errorLabel}>Next</p>
        <p className={styles.errorText} data-testid="website-error-next">
          {parts.next}
        </p>
      </div>
      {onRetry ? (
        <div className="mt-3">
          <Button type="button" size="sm" variant="secondary" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function BlockEditor({
  block,
  depth,
  onChange,
  onReorder,
  onImageReplace,
  uploadingId,
}: {
  block: WebsiteBlock;
  depth: number;
  onChange: (id: string, patch: Partial<WebsiteBlock>) => void;
  onReorder: (id: string, direction: "up" | "down") => void;
  onImageReplace: (id: string, file: File) => void;
  uploadingId: string | null;
}) {
  const pad = { paddingLeft: `${Math.min(depth, 4) * 12}px` };

  return (
    <div
      className={styles.blockCard}
      style={pad}
      data-testid={`website-block-${block.id}`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className={styles.blockKind}>{block.kind}</span>
        {block.kind !== "locked" && block.kind !== "section" ? (
          <div className="flex gap-1">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label="Move block up"
              data-testid={`reorder-up-${block.id}`}
              onClick={() => onReorder(block.id, "up")}
            >
              <ChevronUp className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label="Move block down"
              data-testid={`reorder-down-${block.id}`}
              onClick={() => onReorder(block.id, "down")}
            >
              <ChevronDown className="h-4 w-4" />
            </Button>
          </div>
        ) : null}
      </div>

      {block.kind === "locked" ? (
        <>
          <Callout variant="warning" title="Locked XML">
            Unrecognized snippet stays verbatim. Edit it in Odoo&apos;s website
            editor if you need structural changes.
          </Callout>
          <pre className={styles.lockedXml}>{block.locked_xml}</pre>
        </>
      ) : null}

      {block.kind === "section" && block.children?.length ? (
        <div className="mt-2 space-y-2">
          {block.children.map((child) => (
            <BlockEditor
              key={child.id}
              block={child}
              depth={depth + 1}
              onChange={onChange}
              onReorder={onReorder}
              onImageReplace={onImageReplace}
              uploadingId={uploadingId}
            />
          ))}
        </div>
      ) : null}

      {(block.kind === "heading" ||
        block.kind === "paragraph" ||
        block.kind === "link" ||
        block.kind === "button") && (
        <div className="space-y-2">
          <Input
            label="Text"
            value={block.text ?? ""}
            onChange={(e) => onChange(block.id, { text: e.target.value })}
            data-testid={`block-text-${block.id}`}
          />
          {(block.kind === "link" || block.kind === "button") && (
            <Input
              label="Href"
              value={block.href ?? ""}
              onChange={(e) => onChange(block.id, { href: e.target.value })}
              data-testid={`block-href-${block.id}`}
            />
          )}
        </div>
      )}

      {block.kind === "image" ? (
        <div className="space-y-2">
          {block.src ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={block.src}
              alt=""
              className="max-h-32 rounded border border-border-subtle object-contain"
            />
          ) : null}
          <Input
            label="Image URL"
            value={block.src ?? ""}
            onChange={(e) => onChange(block.id, { src: e.target.value })}
            data-testid={`block-src-${block.id}`}
          />
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium text-muted">
              Replace image
            </span>
            <input
              type="file"
              accept="image/*"
              className="text-sm"
              data-testid={`block-upload-${block.id}`}
              disabled={uploadingId === block.id}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onImageReplace(block.id, file);
              }}
            />
          </label>
        </div>
      ) : null}
    </div>
  );
}

export function WebsiteEditor({
  connectionId,
  pages,
  pagesAvailable,
  unavailableReason,
  pagesLoading = false,
  onRefreshPages,
  initialState,
  onSaved,
}: Props) {
  const [state, setState] = useState<PageState | null>(initialState ?? null);
  const [loadingPage, setLoadingPage] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [errorParts, setErrorParts] = useState<WebsiteErrorParts | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const lockedCount = useMemo(
    () => (state ? countLocked(state.blocks) : 0),
    [state],
  );

  const setRawError = useCallback((raw: string) => {
    setErrorParts(formatWebsiteError(raw));
  }, []);

  const loadPage = useCallback(
    async (pageId: number) => {
      if (initialState?.pageId === pageId) return;
      setLoadingPage(pageId);
      setErrorParts(null);
      setNote(null);
      try {
        const body = await api.getWebsitePageBlocks(connectionId, pageId);
        setState({
          pageId: body.page_id,
          viewId: body.view_id,
          name: body.name,
          url: body.url,
          isPublished: body.is_published,
          blocks: body.blocks as WebsiteBlock[],
        });
      } catch (e) {
        setRawError(e instanceof Error ? e.message : "Failed to load page");
      } finally {
        setLoadingPage(null);
      }
    },
    [connectionId, initialState?.pageId, setRawError],
  );

  async function saveBlocks() {
    if (!state) return;
    setSaving(true);
    setErrorParts(null);
    try {
      const gate = refuseUnsafeWebsiteSave({ blocks: state.blocks });
      if (gate) {
        setRawError(gate);
        return;
      }
      await api.saveWebsitePageBlocks(connectionId, state.pageId, {
        page_id: state.pageId,
        view_id: state.viewId,
        blocks: state.blocks,
      });
      const msg = "Page saved";
      setNote(msg);
      onSaved?.(msg);
    } catch (e) {
      setRawError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function togglePublish() {
    if (!state) return;
    setPublishing(true);
    setErrorParts(null);
    const next = !state.isPublished;
    try {
      await api.publishWebsitePage(connectionId, state.pageId, next);
      setState((prev) => (prev ? { ...prev, isPublished: next } : prev));
      setNote(next ? "Page published" : "Page unpublished");
    } catch (e) {
      setRawError(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setPublishing(false);
    }
  }

  async function replaceImage(blockId: string, file: File) {
    setUploadingId(blockId);
    setErrorParts(null);
    try {
      const uploaded = await api.uploadWebsiteImage(connectionId, file);
      setState((prev) =>
        prev
          ? {
              ...prev,
              blocks: updateBlockTree(prev.blocks, blockId, {
                src: uploaded.src,
              }),
            }
          : prev,
      );
      setNote(`Image uploaded (${uploaded.name})`);
    } catch (e) {
      setRawError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploadingId(null);
    }
  }

  function patchBlock(id: string, patch: Partial<WebsiteBlock>) {
    setState((prev) =>
      prev ? { ...prev, blocks: updateBlockTree(prev.blocks, id, patch) } : prev,
    );
  }

  function reorderBlock(id: string, direction: "up" | "down") {
    setState((prev) =>
      prev
        ? {
            ...prev,
            blocks: reorderSibling(cloneBlocks(prev.blocks), id, direction),
          }
        : prev,
    );
  }

  return (
    <div
      className={`${styles.page} mx-auto max-w-5xl space-y-5`}
      data-testid="website-editor"
    >
      <PageHeader
        title="Website content"
        description="Edit headings, paragraphs, links, buttons, and images on a paper canvas — the same safety checks as reports and mail."
      />

      <Callout variant="info" title="Scope and Online limits" testId="website-honesty-scope">
        Full drag-drop website building stays in Odoo&apos;s editor. Here you edit
        recognized content blocks only. Free HTML invent, script, t-raw, and
        javascript: URLs are refused on save. Placeholders and complex snippets
        that this surface does not recognize stay locked.
      </Callout>

      {!pagesAvailable ? (
        <Callout variant="warning" title="Website module not available">
          {unavailableReason ??
            "Install the website module on this Odoo instance to edit pages here."}
        </Callout>
      ) : null}

      {errorParts ? <WebsiteErrorCard parts={errorParts} /> : null}
      {note ? (
        <Callout variant="info" title="Status">
          {note}
        </Callout>
      ) : null}

      {pagesAvailable ? (
        <div className={styles.workbench} data-testid="website-workbench">
          <div className={styles.listPane}>
            <div className={styles.listHead}>
              <p className={styles.listHeadLabel}>Pages</p>
              <p className={styles.listHeadMeta}>
                {pagesLoading ? "Reading website pages…" : `${pages.length} page${pages.length === 1 ? "" : "s"}`}
              </p>
            </div>
            <div className={styles.listBody}>
              {pagesLoading ? (
                <div className="space-y-2 p-2" data-testid="website-page-list-loading">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </div>
              ) : pages.length === 0 ? (
                <div className={styles.emptyDesk} data-testid="website-page-list-empty">
                  <EmptyState
                    title="No website pages found"
                    description="Install the Website app on Odoo and publish at least one page to edit content here."
                    action={
                      onRefreshPages ? (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={onRefreshPages}
                        >
                          Refresh page list
                        </Button>
                      ) : undefined
                    }
                  />
                </div>
              ) : (
                <ul className="space-y-0.5" data-testid="website-page-list">
                  {pages.map((p) => (
                    <li key={p.id}>
                      <button
                        type="button"
                        className={cn(
                          styles.listRow,
                          state?.pageId === p.id && styles.listRowActive,
                        )}
                        data-testid={`website-page-${p.id}`}
                        disabled={loadingPage === p.id}
                        onClick={() => loadPage(p.id)}
                      >
                        <span className={styles.listRowTitle}>
                          {p.name || `Page ${p.id}`}
                        </span>
                        <span className={styles.listRowMeta}>
                          {p.url || "—"}
                          {p.is_published === false ? " · draft" : ""}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className={styles.editorPane}>
            {state ? (
              <div data-testid="website-editor-panel">
                <div className={styles.editorToolbar}>
                  <div className={styles.editorToolbarTitle}>
                    <p className={styles.editorToolbarName}>{state.name}</p>
                    {state.url ? (
                      <p className={styles.editorToolbarUrl}>{state.url}</p>
                    ) : null}
                  </div>
                  <span
                    className="text-sm text-muted"
                    data-testid="website-publish-label"
                  >
                    {state.isPublished ? "Published" : "Unpublished"}
                  </span>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    loading={publishing}
                    data-testid="website-publish-toggle"
                    onClick={togglePublish}
                  >
                    {state.isPublished ? "Unpublish" : "Publish"}
                  </Button>
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    loading={saving}
                    data-testid="website-save"
                    onClick={() => void saveBlocks()}
                  >
                    Save page
                  </Button>
                </div>

                <div className={styles.editorBody}>
                  {lockedCount > 0 ? (
                    <Callout
                      variant="warning"
                      title={`${lockedCount} locked snippet${lockedCount === 1 ? "" : "s"}`}
                      className="mb-3"
                      testId="website-honesty-locked"
                    >
                      Unrecognized XML stays locked and is written back verbatim.
                      The shared unsafe gate still refuses script, t-raw, t-out,
                      and javascript: URLs inside locked regions on save.
                    </Callout>
                  ) : null}

                  <WebsitePaperPreview
                    name={state.name}
                    url={state.url}
                    blocks={state.blocks}
                  />

                  <div className={styles.blocksPanel}>
                    {state.blocks.map((b) => (
                      <BlockEditor
                        key={b.id}
                        block={b}
                        depth={0}
                        onChange={patchBlock}
                        onReorder={reorderBlock}
                        onImageReplace={replaceImage}
                        uploadingId={uploadingId}
                      />
                    ))}
                  </div>
                </div>

                <div className={styles.editorFooter}>
                  <span className="font-mono text-[0.625rem] text-muted">
                    view #{state.viewId} · page #{state.pageId}
                  </span>
                  <span className="text-xs text-muted">
                    Online: drag-drop builder stays in Odoo — this surface edits
                    grounded content blocks only.
                  </span>
                </div>
              </div>
            ) : (
              <div className={styles.emptyDesk} data-testid="website-editor-empty">
                <p className="p-6 text-sm text-muted">
                  Select a page from the list to open it on the paper desk.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

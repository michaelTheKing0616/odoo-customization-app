"use client";

import { useCallback, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input } from "@/components/ui/Input";
import { ChevronDown, ChevronUp } from "@/components/ui/icons";
import { PageHeader } from "@/components/ui/layout-primitives";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";

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
      className="rounded-md border border-border-subtle bg-surface-raised p-3"
      style={pad}
      data-testid={`website-block-${block.id}`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted">
          {block.kind}
        </span>
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
        <pre className="overflow-x-auto text-xs text-muted">{block.locked_xml}</pre>
      ) : null}

      {block.kind === "section" && block.children?.length ? (
        <div className="space-y-2">
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
            <span className="mb-1 block text-xs font-medium text-muted">Replace image</span>
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
  initialState,
  onSaved,
}: Props) {
  const [state, setState] = useState<PageState | null>(initialState ?? null);
  const [loadingPage, setLoadingPage] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const loadPage = useCallback(
    async (pageId: number) => {
      if (initialState?.pageId === pageId) return;
      setLoadingPage(pageId);
      setError(null);
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
        setError(e instanceof Error ? e.message : "Failed to load page");
      } finally {
        setLoadingPage(null);
      }
    },
    [connectionId, initialState?.pageId],
  );

  async function saveBlocks() {
    if (!state) return;
    setSaving(true);
    setError(null);
    try {
      await api.saveWebsitePageBlocks(connectionId, state.pageId, {
        page_id: state.pageId,
        view_id: state.viewId,
        blocks: state.blocks,
      });
      const msg = "Page saved";
      setNote(msg);
      onSaved?.(msg);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function togglePublish() {
    if (!state) return;
    setPublishing(true);
    setError(null);
    const next = !state.isPublished;
    try {
      await api.publishWebsitePage(connectionId, state.pageId, next);
      setState((prev) => (prev ? { ...prev, isPublished: next } : prev));
      setNote(next ? "Page published" : "Page unpublished");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setPublishing(false);
    }
  }

  async function replaceImage(blockId: string, file: File) {
    setUploadingId(blockId);
    setError(null);
    try {
      const uploaded = await api.uploadWebsiteImage(connectionId, file);
      setState((prev) =>
        prev
          ? {
              ...prev,
              blocks: updateBlockTree(prev.blocks, blockId, { src: uploaded.src }),
            }
          : prev,
      );
      setNote(`Image uploaded (${uploaded.name})`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
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
        ? { ...prev, blocks: reorderSibling(cloneBlocks(prev.blocks), id, direction) }
        : prev,
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6" data-testid="website-editor">
      <PageHeader
        title="Website content"
        description="Edit headings, paragraphs, links, buttons, and images on installed website pages."
      />
      <Callout variant="info" title="Scope">
        Full drag-drop website building stays in Odoo&apos;s editor — this covers content edits
        on recognized blocks. Unrecognized snippets remain locked verbatim.
      </Callout>

      {!pagesAvailable ? (
        <Callout variant="warning" title="Website module not available">
          {unavailableReason ??
            "Install the website module on this Odoo instance to edit pages here."}
        </Callout>
      ) : null}

      {error ? (
        <Callout variant="warning" title="Error">
          {error}
        </Callout>
      ) : null}
      {note ? (
        <Callout variant="info" title="Status">
          {note}
        </Callout>
      ) : null}

      {pagesAvailable ? (
        <ul className="space-y-1" data-testid="website-page-list">
          {pages.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className={cn(
                  "text-left text-sm underline-offset-2 hover:underline",
                  state?.pageId === p.id ? "font-medium text-accent" : "text-accent",
                )}
                data-testid={`website-page-${p.id}`}
                disabled={loadingPage === p.id}
                onClick={() => loadPage(p.id)}
              >
                {p.name} {p.url ? `(${p.url})` : ""}
                {p.is_published === false ? " · draft" : ""}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {state ? (
        <div className="space-y-4" data-testid="website-editor-panel">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-ink">{state.name}</h2>
              {state.url ? <p className="text-sm text-muted">{state.url}</p> : null}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted" data-testid="website-publish-label">
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
                onClick={saveBlocks}
              >
                Save page
              </Button>
            </div>
          </div>

          <div className="space-y-3">
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
      ) : null}
    </div>
  );
}

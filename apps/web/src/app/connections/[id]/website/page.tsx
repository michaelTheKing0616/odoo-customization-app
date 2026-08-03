"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { Callout } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/layout-primitives";
import { api } from "@/lib/api";

type Block = {
  id: string;
  kind: string;
  text?: string;
  href?: string;
  locked_xml?: string;
};

export default function WebsiteEditorPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const [pages, setPages] = useState<
    Array<{ id: number; name: string | null; url: string | null }>
  >([]);
  const [selectedPage, setSelectedPage] = useState<number | null>(null);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [viewId, setViewId] = useState<number | null>(null);

  useEffect(() => {
    api
      .listWebsitePages(connectionId)
      .then((res) => setPages(res.pages ?? []))
      .catch((e: Error) => setError(e.message));
  }, [connectionId]);

  const loadBlocks = useCallback(
    async (pageId: number) => {
      setSelectedPage(pageId);
      setNote(null);
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/connections/${connectionId}/website/pages/${pageId}/blocks`,
        { headers: { "Content-Type": "application/json" } },
      );
      if (!res.ok) {
        setError(await res.text());
        return;
      }
      const body = await res.json();
      setBlocks(body.blocks ?? []);
      setViewId(body.view_id ?? null);
    },
    [connectionId],
  );

  async function saveBlocks() {
    if (selectedPage == null || viewId == null) return;
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/connections/${connectionId}/website/pages/${selectedPage}/blocks`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_id: selectedPage, view_id: viewId, blocks }),
      },
    );
    setNote(res.ok ? "Saved" : await res.text());
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6" data-testid="website-editor-page">
      <PageHeader
        title="Website content"
        description="Edit headings, paragraphs, links, and images on installed website pages."
      />
      <Callout variant="info" title="Scope">
        Full drag-drop website building stays in Odoo&apos;s editor — this covers content edits
        on recognized blocks. Unrecognized snippets remain locked verbatim.
      </Callout>
      {error && (
        <Callout variant="warning" title="Error">
          {error}
        </Callout>
      )}
      {note && (
        <Callout variant="info" title="Saved">
          {note}
        </Callout>
      )}
      <ul className="space-y-2">
        {pages.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              className="text-left text-sm text-[var(--oc-accent)] underline"
              onClick={() => loadBlocks(p.id)}
            >
              {p.name} {p.url ? `(${p.url})` : ""}
            </button>
          </li>
        ))}
      </ul>
      {blocks.map((b) => (
        <div key={b.id} className="rounded border border-[var(--oc-border)] p-3">
          <div className="text-xs text-[var(--oc-muted)]">{b.kind}</div>
          {b.kind === "locked" ? (
            <pre className="mt-2 overflow-x-auto text-xs">{b.locked_xml}</pre>
          ) : (
            <input
              className="mt-2 w-full rounded border px-2 py-1 text-sm"
              value={b.text ?? ""}
              onChange={(e) =>
                setBlocks((prev) =>
                  prev.map((x) => (x.id === b.id ? { ...x, text: e.target.value } : x)),
                )
              }
            />
          )}
        </div>
      ))}
      {selectedPage != null && (
        <button
          type="button"
          className="rounded bg-[var(--oc-accent)] px-4 py-2 text-sm text-white"
          onClick={saveBlocks}
        >
          Save page
        </button>
      )}
    </div>
  );
}

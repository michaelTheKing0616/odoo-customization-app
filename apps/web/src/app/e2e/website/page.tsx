"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";
import {
  WebsiteEditor,
  type WebsiteBlock,
  type WebsitePageSummary,
} from "@/components/website/WebsiteEditor";
import { WebsitePaperPreview } from "@/components/website/WebsitePaperPreview";
import styles from "@/components/website/WebsitePage.module.css";

/**
 * DOC-WEBSITE vision harness — paper desk + page list. Gated by NEXT_PUBLIC_E2E.
 */
type Shot = "desktop" | "empty" | "locked" | "error";

const MOCK_BLOCKS: WebsiteBlock[] = [
  {
    id: "sec-1",
    kind: "section",
    children: [
      { id: "h-1", kind: "heading", level: 2, text: "Welcome" },
      { id: "p-1", kind: "paragraph", text: "Hello world" },
      { id: "a-1", kind: "link", text: "Contact", href: "/contact" },
      { id: "img-1", kind: "image", src: "/web/image/1" },
      { id: "locked-1", kind: "locked", locked_xml: '<t t-foreach="items" t-as="item"/>' },
    ],
  },
];

const PAGES: WebsitePageSummary[] = [
  { id: 1, name: "Home", url: "/", is_published: true },
  { id: 2, name: "About", url: "/about", is_published: false },
];

export default function WebsiteHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [shot, setShot] = useState<Shot>("desktop");

  const pages = useMemo(() => (shot === "empty" ? [] : PAGES), [shot]);
  const blocks = useMemo(() => {
    if (shot === "error") {
      return [
        {
          id: "sec-1",
          kind: "section",
          children: [
            { id: "p-1", kind: "paragraph", text: "Hello" },
            {
              id: "locked-bad",
              kind: "locked",
              locked_xml: "<script>evil()</script>",
            },
          ],
        },
      ] as WebsiteBlock[];
    }
    return MOCK_BLOCKS;
  }, [shot]);

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main className={`${styles.page} mx-auto max-w-5xl p-6`} data-testid="website-harness">
      <PageHeader
        title="Website (vision)"
        description="DOC-WEBSITE harness — pasteboard page paper, shared unsafe gate."
      />
      <div className="mt-4 flex flex-wrap gap-2">
        {(["desktop", "empty", "locked", "error"] as Shot[]).map((s) => (
          <Button
            key={s}
            type="button"
            size="sm"
            variant={shot === s ? "primary" : "secondary"}
            onClick={() => setShot(s)}
            data-testid={`shot-${s}`}
          >
            {s}
          </Button>
        ))}
      </div>

      <div className="mt-6">
        {shot === "locked" ? (
          <WebsitePaperPreview name="Home" url="/" blocks={MOCK_BLOCKS} />
        ) : (
          <WebsiteEditor
            connectionId="e2e-connection"
            pages={pages}
            pagesAvailable
            pagesLoading={false}
            initialState={
              shot === "empty"
                ? undefined
                : {
                    pageId: 1,
                    viewId: 10,
                    name: "Home",
                    url: "/",
                    isPublished: true,
                    blocks,
                  }
            }
          />
        )}
      </div>
    </main>
  );
}

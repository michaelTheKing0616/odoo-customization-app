"use client";

import { WebsiteEditor, type WebsiteBlock } from "@/components/website/WebsiteEditor";

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

/** E2E harness for website editor without live Odoo. */
export default function WebsiteHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main className="p-6" data-testid="website-harness">
      <WebsiteEditor
        connectionId="e2e-connection"
        pages={[{ id: 1, name: "Home", url: "/", is_published: true }]}
        pagesAvailable
        initialState={{
          pageId: 1,
          viewId: 10,
          name: "Home",
          url: "/",
          isPublished: true,
          blocks: MOCK_BLOCKS,
        }}
      />
    </main>
  );
}

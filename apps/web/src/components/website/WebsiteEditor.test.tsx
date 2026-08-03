/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WebsiteEditor, type WebsiteBlock } from "@/components/website/WebsiteEditor";

vi.mock("@/lib/api", () => ({
  api: {
    getWebsitePageBlocks: vi.fn(),
    saveWebsitePageBlocks: vi.fn(async () => ({ ok: true, view_id: 10, arch_len: 42 })),
    publishWebsitePage: vi.fn(async () => ({ ok: true, page_id: 1, is_published: false })),
    uploadWebsiteImage: vi.fn(async () => ({
      attachment_id: 99,
      src: "/web/image/99",
      name: "hero.png",
    })),
  },
}));

const BLOCKS: WebsiteBlock[] = [
  {
    id: "sec-1",
    kind: "section",
    children: [
      { id: "p-1", kind: "paragraph", text: "Hello" },
      { id: "a-1", kind: "link", text: "Go", href: "/go" },
    ],
  },
];

describe("WebsiteEditor", () => {
  afterEach(() => cleanup());

  it("renders harness blocks and saves", async () => {
    render(
      <WebsiteEditor
        connectionId="conn"
        pages={[{ id: 1, name: "Home", url: "/" }]}
        pagesAvailable
        initialState={{
          pageId: 1,
          viewId: 10,
          name: "Home",
          url: "/",
          isPublished: true,
          blocks: BLOCKS,
        }}
      />,
    );
    expect(screen.getByTestId("website-editor-panel")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("block-text-p-1"), {
      target: { value: "Updated" },
    });
    fireEvent.click(screen.getByTestId("website-save"));
    await waitFor(() => {
      expect(screen.getByText("Page saved")).toBeInTheDocument();
    });
  });

  it("toggles publish state", async () => {
    render(
      <WebsiteEditor
        connectionId="conn"
        pages={[{ id: 1, name: "Home", url: "/" }]}
        pagesAvailable
        initialState={{
          pageId: 1,
          viewId: 10,
          name: "Home",
          url: "/",
          isPublished: true,
          blocks: BLOCKS,
        }}
      />,
    );
    fireEvent.click(screen.getByTestId("website-publish-toggle"));
    await waitFor(() => {
      expect(screen.getByText("Page unpublished")).toBeInTheDocument();
    });
  });
});

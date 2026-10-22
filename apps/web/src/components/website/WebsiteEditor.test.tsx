/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WebsiteEditor, type WebsiteBlock } from "@/components/website/WebsiteEditor";
import { api } from "@/lib/api";

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
      {
        id: "locked-1",
        kind: "locked",
        locked_xml: '<t t-foreach="items" t-as="item"/>',
      },
    ],
  },
];

const UNSAFE_BLOCKS: WebsiteBlock[] = [
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
];

describe("WebsiteEditor", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders harness blocks, paper, and saves", async () => {
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
    expect(screen.getByTestId("website-paper-preview")).toBeInTheDocument();
    expect(screen.getByTestId("website-honesty-locked")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("block-text-p-1"), {
      target: { value: "Updated" },
    });
    fireEvent.click(screen.getByTestId("website-save"));
    await waitFor(() => {
      expect(screen.getByText("Page saved")).toBeInTheDocument();
    });
    expect(api.saveWebsitePageBlocks).toHaveBeenCalled();
  });

  it("refuses unsafe locked XML on save with what / why / next", async () => {
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
          blocks: UNSAFE_BLOCKS,
        }}
      />,
    );
    fireEvent.click(screen.getByTestId("website-save"));
    await waitFor(() => {
      expect(screen.getByTestId("website-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("website-error-what").textContent).toMatch(/unsafe gate/i);
    expect(screen.getByTestId("website-error-why").textContent).toMatch(/script/i);
    expect(screen.getByTestId("website-error-next").textContent).toMatch(/Remove script|save again/i);
    expect(api.saveWebsitePageBlocks).not.toHaveBeenCalled();
  });

  it("shows empty page list without Loading... copy", () => {
    const onRefresh = vi.fn();
    render(
      <WebsiteEditor
        connectionId="conn"
        pages={[]}
        pagesAvailable
        pagesLoading={false}
        onRefreshPages={onRefresh}
      />,
    );
    expect(screen.getByRole("heading", { name: "No website pages found" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh page list" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  it("shows skeleton while pages load without Loading... copy", () => {
    render(
      <WebsiteEditor connectionId="conn" pages={[]} pagesAvailable pagesLoading />,
    );
    expect(screen.getByTestId("website-page-list-loading")).toBeInTheDocument();
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
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

  it("shows honesty scope banner", () => {
    render(
      <WebsiteEditor connectionId="conn" pages={[]} pagesAvailable />,
    );
    expect(screen.getByTestId("website-honesty-scope")).toBeInTheDocument();
  });
});

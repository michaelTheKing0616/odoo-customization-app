/** @vitest-environment jsdom */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ShellProvider, useShell } from "@/context/ShellContext";
import { TooltipProvider } from "@/components/ui/Tooltip";
import type { ExpertAskResponse } from "@/lib/api";
import { ExpertBubble } from "./ExpertBubble";
import { ExpertDestination } from "./ExpertDestination";
import { ExpertPanel } from "./ExpertPanel";

vi.mock("@/styles/studio-refinement.css", () => ({}));

const nav = vi.hoisted(() => ({ pathname: "/connections/conn-1/builder" }));
vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    expertSuggestedPrompts: vi.fn().mockResolvedValue([]),
    expertAsk: vi.fn(),
    expertIntentRoute: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const ANSWER: ExpertAskResponse = {
  answer_markdown: "Use an inherited view with an XPath position [1].",
  citations: [
    { source: "odoo_docs", version: "19.0", breadcrumb: "Views", chunk_id: "c1", source_index: 1 },
  ],
  grounded: true,
  declined: false,
  suggested_tools: [],
  caution_flags: [],
  reasoning: false,
  uncited_warning: false,
};

function ShellProbe() {
  const { expertOpen, openExpert } = useShell();
  return (
    <>
      <span data-testid="probe-open">{expertOpen ? "open" : "closed"}</span>
      <button
        type="button"
        onClick={() => openExpert({ question: "Why AccessError on x_visitor?", autoSubmit: true })}
      >
        Diagnose from elsewhere
      </button>
      <button type="button" onClick={() => openExpert()}>
        Open from top bar
      </button>
    </>
  );
}

function renderWithShell(ui: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ShellProvider connectionId="conn-1">
        <TooltipProvider>
          <ShellProbe />
          {ui}
        </TooltipProvider>
      </ShellProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(api.expertAsk).mockReset();
});

afterEach(() => {
  cleanup();
  nav.pathname = "/connections/conn-1/builder";
});

describe("Expert surfaces (UI-S-25)", () => {
  it("renders the same conversation component in the drawer and on the page", async () => {
    const { unmount } = renderWithShell(<ExpertPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Open from top bar" }));
    const dialog = await screen.findByRole("dialog", { name: "Odoo Expert" });
    const drawerConversation = within(dialog).getByTestId("expert-conversation");
    expect(drawerConversation).toHaveAttribute("data-surface", "drawer");
    unmount();

    nav.pathname = "/connections/conn-1/expert";
    renderWithShell(<ExpertPanel variant="page" />);
    const pageConversation = screen.getByTestId("expert-conversation");
    expect(pageConversation).toHaveAttribute("data-surface", "page");
    expect(screen.queryByRole("dialog")).toBeNull();

    // Same building blocks on both surfaces.
    for (const id of ["expert-context-bar", "expert-thread", "expert-input"]) {
      expect(within(pageConversation).getByTestId(id)).toBeInTheDocument();
    }
    expect(within(pageConversation).getByRole("button", { name: "Ask Expert" })).toBeInTheDocument();
  });

  it("stands the shell drawer and launcher down on the Expert page", () => {
    nav.pathname = "/connections/conn-1/expert";
    renderWithShell(
      <>
        <ExpertPanel />
        <ExpertBubble />
      </>,
    );
    expect(screen.queryByTestId("expert-panel")).toBeNull();
    expect(screen.queryByTestId("open-expert")).toBeNull();
  });

  it("keeps the drawer and launcher on every other route", () => {
    renderWithShell(
      <>
        <ExpertPanel />
        <ExpertBubble />
      </>,
    );
    expect(screen.getByTestId("expert-panel")).toBeInTheDocument();
    expect(screen.getByTestId("open-expert")).toBeInTheDocument();
  });

  it("answers openExpert prefills inline on the page without leaving the drawer flag set", async () => {
    nav.pathname = "/connections/conn-1/expert";
    vi.mocked(api.expertAsk).mockResolvedValue(ANSWER);
    renderWithShell(<ExpertPanel variant="page" />);

    fireEvent.click(screen.getByRole("button", { name: "Diagnose from elsewhere" }));
    await screen.findByText(/inherited view with an XPath position/);
    expect(api.expertAsk).toHaveBeenCalledWith(
      expect.objectContaining({ question: "Why AccessError on x_visitor?", connection_id: "conn-1" }),
    );
    await waitFor(() => expect(screen.getByTestId("probe-open")).toHaveTextContent("closed"));

    fireEvent.click(screen.getByRole("button", { name: "Open from top bar" }));
    await waitFor(() => expect(screen.getByTestId("probe-open")).toHaveTextContent("closed"));
    await waitFor(() => expect(screen.getByTestId("expert-input")).toHaveFocus());
  });

  it("keeps a failed question and re-asks it once with Ask again", async () => {
    nav.pathname = "/connections/conn-1/expert";
    vi.mocked(api.expertAsk)
      .mockRejectedValueOnce(new Error("Expert retrieval timed out after 60s"))
      .mockResolvedValueOnce(ANSWER);
    renderWithShell(<ExpertPanel variant="page" />);

    fireEvent.change(screen.getByTestId("expert-input"), {
      target: { value: "How do I extend the partner form?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask Expert" }));

    const error = await screen.findByTestId("expert-error");
    expect(error).toHaveTextContent("Expert could not answer");
    expect(error).toHaveTextContent(/timed out/);
    expect(error).toHaveTextContent(/Your question is kept/);

    fireEvent.click(within(error).getByRole("button", { name: "Ask again" }));
    await screen.findByText(/inherited view with an XPath position/);
    expect(screen.queryByTestId("expert-error")).toBeNull();
    expect(screen.getAllByText("How do I extend the partner form?")).toHaveLength(1);
    expect(api.expertAsk).toHaveBeenCalledTimes(2);
  });

  it("lands a new answer with its question at the top of the thread, not at the end", async () => {
    nav.pathname = "/connections/conn-1/expert";
    vi.mocked(api.expertAsk).mockResolvedValue(ANSWER);
    const scrollTo = vi.fn();
    const proto = HTMLElement.prototype;
    const ownScrollTo = Object.getOwnPropertyDescriptor(proto, "scrollTo");
    const ownRect = Object.getOwnPropertyDescriptor(proto, "getBoundingClientRect");
    HTMLElement.prototype.scrollTo = scrollTo as unknown as typeof HTMLElement.prototype.scrollTo;
    HTMLElement.prototype.getBoundingClientRect = function (this: HTMLElement) {
      const top = this.classList.contains("expert-turn-user") ? 420 : 100;
      return { top, left: 0, right: 0, bottom: top, width: 0, height: 0, x: 0, y: top } as DOMRect;
    };
    try {
      renderWithShell(<ExpertPanel variant="page" />);
      fireEvent.change(screen.getByTestId("expert-input"), {
        target: { value: "How do I extend the partner form?" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Ask Expert" }));
      await screen.findByText(/inherited view with an XPath position/);
      // Question sits 320px below the thread top; it is pinned 16px from the top.
      await waitFor(() =>
        expect(scrollTo).toHaveBeenLastCalledWith(expect.objectContaining({ top: 304 })),
      );
    } finally {
      if (ownScrollTo) Object.defineProperty(proto, "scrollTo", ownScrollTo);
      else delete (proto as Partial<HTMLElement>).scrollTo;
      if (ownRect) Object.defineProperty(proto, "getBoundingClientRect", ownRect);
      else delete (proto as Partial<HTMLElement>).getBoundingClientRect;
    }
  });

  it("offers curated starters when the server has no suggested prompts", async () => {
    nav.pathname = "/connections/conn-1/expert";
    renderWithShell(<ExpertPanel variant="page" />);
    const list = await screen.findByTestId("expert-suggested-prompts");
    expect(within(list).getByRole("button", { name: "Form extension (XPath)" })).toBeInTheDocument();
    expect(within(list).getAllByRole("button").length).toBeLessThanOrEqual(4);
  });
});

describe("ExpertDestination", () => {
  it("makes Ask Expert the only filled primary and keeps the honesty legend", async () => {
    nav.pathname = "/connections/conn-1/expert";
    renderWithShell(<ExpertDestination connectionId="conn-1" connectionName="Lab 19" />);

    const page = screen.getByTestId("expert-destination");
    await screen.findByTestId("expert-suggested-prompts");
    const primaries = Array.from(page.querySelectorAll("button, a")).filter((el) =>
      el.className.split(/\s+/).includes("bg-accent"),
    );
    expect(primaries.map((el) => el.textContent?.trim())).toEqual(["Ask Expert"]);

    expect(screen.getByRole("heading", { level: 1, name: "Odoo Expert" })).toBeInTheDocument();
    expect(screen.getByText(/^Lab 19 · Grounded answers/)).toBeInTheDocument();
    expect(screen.getByTestId("expert-overview-honesty")).toHaveTextContent(
      "A complete draft is not the same as certified, and neither means Autopilot-ready. Expert never publishes on its own.",
    );
    expect(screen.getByTestId("expert-overview-legend")).toHaveTextContent(/Expert is a copilot/);
    expect(screen.getByTestId("intent-router-submit")).toHaveTextContent("Find feature");
    expect(within(screen.getByTestId("intent-router-starters")).getAllByRole("button")).toHaveLength(4);
  });
});

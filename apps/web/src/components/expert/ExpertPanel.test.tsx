/** @vitest-environment jsdom */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ShellProvider, useShell } from "@/context/ShellContext";
import { ExpertPanel } from "./ExpertPanel";

vi.mock("@/styles/studio-refinement.css", () => ({}));

vi.mock("@/lib/api", () => ({
  api: {
    expertSuggestedPrompts: vi.fn().mockResolvedValue([]),
    expertAsk: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function ExpertOpener() {
  const { setExpertOpen } = useShell();
  return (
    <button type="button" onClick={() => setExpertOpen(true)}>
      Open expert
    </button>
  );
}

function renderExpert() {
  return render(
    <QueryClientProvider client={queryClient}>
      <ShellProvider connectionId="conn-1">
        <ExpertOpener />
        <ExpertPanel />
      </ShellProvider>
    </QueryClientProvider>,
  );
}

function expectExpertClosed() {
  expect(screen.queryByRole("dialog", { name: "Odoo Expert" })).not.toBeInTheDocument();
}

describe("ExpertPanel", () => {
  it("opens and closes, and Escape and the backdrop dismiss it", async () => {
    renderExpert();
    expectExpertClosed();

    fireEvent.click(screen.getByRole("button", { name: "Open expert" }));
    const dialog = await screen.findByRole("dialog", { name: "Odoo Expert" });
    expect(screen.getByTestId("expert-panel")).toContainElement(dialog);
    expect(screen.getByTestId("motion-sheet-panel")).toBe(dialog);
    expect(screen.getByTestId("expert-header")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New thread" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask Expert" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close panel" }));
    await waitFor(expectExpertClosed);

    fireEvent.click(screen.getByRole("button", { name: "Open expert" }));
    await screen.findByRole("dialog", { name: "Odoo Expert" });
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(expectExpertClosed);

    fireEvent.click(screen.getByRole("button", { name: "Open expert" }));
    await screen.findByRole("dialog", { name: "Odoo Expert" });
    const backdrop = screen.getByTestId("expert-panel").querySelector('[class*="bg-black/40"]');
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop!);
    await waitFor(expectExpertClosed);
  });
});

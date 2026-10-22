/** @vitest-environment happy-dom */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getConnection: vi.fn(),
  listConnections: vi.fn(),
  listModels: vi.fn(),
  expertSuggestedPrompts: vi.fn(),
  expertNLSearch: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/connections/conn-1",
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/context/ShellContext", () => ({
  useShell: () => ({
    commandOpen: false,
    setCommandOpen: vi.fn(),
    setExpertOpen: vi.fn(),
    openExpert: vi.fn(),
    setUiContext: vi.fn(),
    uiContext: {},
  }),
}));
vi.mock("@/lib/api", () => ({ api: mocks }));
vi.mock("@/components/expert/ExpertPanel", () => ({ ExpertPanel: () => null }));
vi.mock("@/components/expert/ExpertBubble", () => ({ ExpertBubble: () => null }));
vi.mock("@/lib/expert-diagnostics", () => ({ ExpertDiagnoseListener: () => null }));

import { AppShell } from "./AppShell";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AppShell connection loading", () => {
  it("shows a shell-shaped skeleton instead of loading text while the connection loads", () => {
    mocks.getConnection.mockReturnValue(new Promise(() => undefined));
    mocks.listConnections.mockReturnValue(new Promise(() => undefined));
    const client = new QueryClient();
    const { container } = render(
      <QueryClientProvider client={client}>
        <AppShell connectionId="conn-1">
          <p>page body</p>
        </AppShell>
      </QueryClientProvider>,
    );

    const loading = screen.getByTestId("app-shell-loading");
    expect(loading).toHaveAttribute("role", "status");
    expect(screen.getByText("Loading this connection.")).toBeInTheDocument();
    expect(container.querySelectorAll(".shimmer-15").length).toBeGreaterThan(8);
    expect(screen.queryByText(/Loading connection…/)).toBeNull();
    expect(screen.queryByText("page body")).toBeNull();
  });
});

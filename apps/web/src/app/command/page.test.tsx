/** @vitest-environment happy-dom */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const replaceMock = vi.fn();

vi.mock("@/components/command/fleet-operate.css", () => ({}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(),
}));

import CommandCenterPage from "@/app/command/page";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  replaceMock.mockReset();
});

function jsonResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: async () => body,
  });
}

describe("command center page", () => {
  it("redirects a client approver to the approval inbox for their connection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => {
        const url = String(input);
        if (url === "/api/accounts/me") {
          return jsonResponse({
            workspace: { role: "client_approver" },
          });
        }
        if (url === "/api/connections") {
          return jsonResponse([{ id: "conn-granted" }]);
        }
        return jsonResponse({}, false, 404);
      }),
    );

    render(<CommandCenterPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/approvals?connection_id=conn-granted");
    });
    expect(screen.queryByTestId("command-tile-clients")).not.toBeInTheDocument();
  });

  it("loads each tile on its own and keeps the page when one source is slow", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => {
        const url = String(input);
        if (url === "/api/accounts/me") {
          return jsonResponse({ workspace: { role: "owner" } });
        }
        if (url === "/api/command/tiles/clients") {
          return jsonResponse({ count: 2 });
        }
        if (url === "/api/command/tiles/pending-approvals") {
          return new Promise(() => {
            /* never resolves — skeleton stays on this tile only */
          });
        }
        if (url === "/api/command/tiles/failed-jobs") {
          return jsonResponse({ count: 1 });
        }
        if (url === "/api/command/tiles/drift") {
          return jsonResponse({ count: 0 });
        }
        return jsonResponse({}, false, 404);
      }),
    );

    render(<CommandCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("command-tile-clients-count")).toHaveTextContent("2");
    });
    expect(screen.getByTestId("command-tile-failed-jobs-count")).toHaveTextContent("1");
    expect(screen.getByTestId("command-tile-drift-count")).toHaveTextContent("0");
    expect(screen.getByTestId("command-tile-pending-approvals-skeleton")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fleet" })).toBeInTheDocument();
    expect(screen.getByTestId("fleet-honesty")).toBeInTheDocument();
    expect(screen.getByTestId("fleet-primary-cta")).toHaveTextContent("Open a client");
  });

  it("shows retry on a failed tile without clearing sibling counts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => {
        const url = String(input);
        if (url === "/api/accounts/me") {
          return jsonResponse({ workspace: { role: "builder" } });
        }
        if (url === "/api/command/tiles/clients") {
          return jsonResponse({ count: 3 });
        }
        if (url === "/api/command/tiles/pending-approvals") {
          return jsonResponse({ count: 0 });
        }
        if (url === "/api/command/tiles/failed-jobs") {
          return Promise.resolve({ ok: false, status: 503, json: async () => ({}) });
        }
        if (url === "/api/command/tiles/drift") {
          return jsonResponse({ count: 1 });
        }
        return jsonResponse({}, false, 404);
      }),
    );

    render(<CommandCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("command-tile-failed-jobs-retry")).toBeInTheDocument();
    });
    expect(screen.getByTestId("command-tile-clients-count")).toHaveTextContent("3");
    expect(screen.getByTestId("command-tile-drift-count")).toHaveTextContent("1");
    expect(screen.getByTestId("fleet-partial-guide")).toBeInTheDocument();
  });

  it("shows empty fleet what/why/next with Connect Odoo primary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => {
        const url = String(input);
        if (url === "/api/accounts/me") {
          return jsonResponse({ workspace: { role: "owner" } });
        }
        if (url.startsWith("/api/command/tiles/")) {
          return jsonResponse({ count: 0 });
        }
        return jsonResponse({}, false, 404);
      }),
    );

    render(<CommandCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("fleet-empty-guide")).toBeInTheDocument();
    });
    expect(screen.getByTestId("fleet-primary-cta")).toHaveTextContent("Connect Odoo");
    expect(screen.getByTestId("fleet-honesty-why").textContent?.toLowerCase()).toContain(
      "never writes across connections",
    );
  });
});

/** @vitest-environment happy-dom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AdminPage from "./page";

function jsonResponse(body: unknown) {
  return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("admin console states", () => {
  it("shows a table skeleton per section while the admin API answers", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => undefined)));
    render(<AdminPage />);

    for (const id of ["admin-users", "admin-workspaces", "admin-telemetry"]) {
      const loading = screen.getByTestId(`${id}-loading`);
      expect(loading).toHaveAttribute("role", "status");
      expect(loading.querySelectorAll(".shimmer-15")).toHaveLength(3);
    }
    expect(screen.getByText("Loading users.")).toBeInTheDocument();
    expect(screen.queryByText("No users yet")).toBeNull();
  });

  it("shows one empty state per section when the lists come back empty", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/trust-telemetry")) return jsonResponse({ workspaces: [] });
        if (url.endsWith("/ga-criteria")) {
          return jsonResponse({
            min_beta_partner_workspaces: 3,
            min_weeks_per_workspace: 4,
            production_write_mode_ga_unlocked: false,
            exit_criteria: [],
          });
        }
        return jsonResponse([]);
      }),
    );
    render(<AdminPage />);

    expect(await screen.findByRole("heading", { name: "No users yet" })).toBeInTheDocument();
    expect(
      screen.getByText("Accounts appear here after someone signs up, with their verification status."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No workspaces yet" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No workspaces to report on" })).toBeInTheDocument();
    expect(screen.queryByTestId("admin-users-loading")).toBeNull();
  });

  it("shows the error instead of empty states when the admin API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 404, text: async () => "Not found", json: async () => ({}) })),
    );
    render(<AdminPage />);

    expect(await screen.findByText(/Not found/)).toBeInTheDocument();
    expect(screen.queryByText("No users yet")).toBeNull();
    expect(screen.queryByTestId("admin-users-loading")).toBeNull();
  });
});

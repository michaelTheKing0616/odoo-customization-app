/** @vitest-environment happy-dom */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ConnectionClientPage from "./page";

const mocks = vi.hoisted(() => ({
  getConnection: vi.fn(),
  listInboxPlans: vi.fn(),
  listSnapshots: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "conn-abc" }),
}));

vi.mock("@/lib/api", () => ({
  api: mocks,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("connections/[id]/client page", () => {
  it("shows connection, open change-sets, last snapshot, and bot roster unavailable", async () => {
    mocks.getConnection.mockResolvedValue({
      id: "conn-abc",
      name: "Acme Odoo",
      url: "https://odoo.example.com",
      db_name: "acme_prod",
      username: "admin",
      server_version: "19.0",
      write_mode: "standard",
      created_at: null,
      updated_at: null,
    });
    mocks.listInboxPlans.mockResolvedValue({
      plans: [
        {
          plan_hash: "hash-pending-1",
          goal: "Add invoice note field",
          status: "pending",
          max_risk: "R2",
          environment: "staging",
          expires_at: "2026-10-06T12:00:00Z",
        },
        {
          plan_hash: "hash-done",
          goal: "Old approved plan",
          status: "approved",
          max_risk: "R1",
          environment: "staging",
          expires_at: "2026-10-01T12:00:00Z",
        },
      ],
    });
    mocks.listSnapshots.mockResolvedValue([
      {
        id: "snap-latest",
        resource_type: "ir.ui.view",
        resource_key: "42",
        label: "sale.order.form",
        reversible: "yes",
        created_at: "2026-10-04T09:00:00Z",
      },
    ]);

    render(<ConnectionClientPage />);

    expect(screen.getByTestId("connection-client-page")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Acme Odoo")).toBeInTheDocument();
    });

    const openPlans = screen.getAllByTestId("connection-client-open-plan");
    expect(openPlans).toHaveLength(1);
    expect(openPlans[0]).toHaveTextContent("Add invoice note field");

    expect(screen.getByText("sale.order.form")).toBeInTheDocument();
    expect(screen.getByText("snap-latest")).toBeInTheDocument();

    expect(screen.getByTestId("connection-client-bot-roster")).toHaveTextContent(
      /not available yet/i,
    );
  });

  it("keeps other sections visible when one section fails", async () => {
    mocks.getConnection.mockRejectedValue(new Error("fail"));
    mocks.listInboxPlans.mockResolvedValue({ plans: [] });
    mocks.listSnapshots.mockResolvedValue([]);

    render(<ConnectionClientPage />);

    await waitFor(() => {
      expect(screen.getByTestId("connection-client-connection-error")).toBeInTheDocument();
    });

    expect(screen.getByTestId("connection-client-changesets")).toBeInTheDocument();
    expect(screen.getByText("No open change-sets")).toBeInTheDocument();
    expect(screen.getByText("No snapshots yet")).toBeInTheDocument();
  });
});

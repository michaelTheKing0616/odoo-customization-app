/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  listConnectionGrants: vi.fn(),
  createConnectionGrant: vi.fn(),
  deleteConnectionGrant: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    listConnectionGrants: mocks.listConnectionGrants,
    createConnectionGrant: mocks.createConnectionGrant,
    deleteConnectionGrant: mocks.deleteConnectionGrant,
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { ConnectionTeamGrantsPanel } from "./ConnectionTeamGrantsPanel";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ConnectionTeamGrantsPanel", () => {
  it("grants access via POST /api/accounts/connection-grants", async () => {
    mocks.listConnectionGrants.mockResolvedValue([]);
    mocks.createConnectionGrant.mockResolvedValue({
      id: "grant-1",
      role: "client_approver",
      connection_id: "conn-a",
    });
    mocks.listConnectionGrants.mockResolvedValueOnce([]).mockResolvedValueOnce([
      {
        id: "grant-1",
        connection_id: "conn-a",
        user_id: "u1",
        email: "client@example.com",
        role: "client_approver",
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);

    render(<ConnectionTeamGrantsPanel connectionId="conn-a" connectionName="Staging" />);

    await waitFor(() => {
      expect(mocks.listConnectionGrants).toHaveBeenCalledWith("conn-a");
    });

    fireEvent.change(screen.getByTestId("connection-grant-email"), {
      target: { value: "client@example.com" },
    });
    fireEvent.click(screen.getByTestId("connection-grant-submit"));

    await waitFor(() => {
      expect(mocks.createConnectionGrant).toHaveBeenCalledWith({
        connection_id: "conn-a",
        email: "client@example.com",
        role: "client_approver",
      });
    });
  });

  it("revokes access via DELETE /api/accounts/connection-grants/{id}", async () => {
    mocks.listConnectionGrants.mockResolvedValue([
      {
        id: "grant-9",
        connection_id: "conn-a",
        user_id: "u9",
        email: "viewer@example.com",
        role: "client_viewer",
        created_at: "2026-01-02T00:00:00Z",
      },
    ]);
    mocks.deleteConnectionGrant.mockResolvedValue(undefined);
    mocks.listConnectionGrants
      .mockResolvedValueOnce([
        {
          id: "grant-9",
          connection_id: "conn-a",
          user_id: "u9",
          email: "viewer@example.com",
          role: "client_viewer",
          created_at: "2026-01-02T00:00:00Z",
        },
      ])
      .mockResolvedValueOnce([]);

    render(<ConnectionTeamGrantsPanel connectionId="conn-a" />);

    await waitFor(() => {
      expect(screen.getByText("viewer@example.com")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("connection-grant-revoke-grant-9"));
    fireEvent.click(screen.getByTestId("connection-grant-revoke-confirm"));

    await waitFor(() => {
      expect(mocks.deleteConnectionGrant).toHaveBeenCalledWith("grant-9");
    });
  });

  it("shows an error when grant fails", async () => {
    mocks.listConnectionGrants.mockResolvedValue([]);
    mocks.createConnectionGrant.mockRejectedValue(new Error("No account for that email yet"));

    render(<ConnectionTeamGrantsPanel connectionId="conn-a" />);

    await waitFor(() => {
      expect(screen.getByTestId("connection-grant-submit")).not.toBeDisabled();
    });

    fireEvent.change(screen.getByTestId("connection-grant-email"), {
      target: { value: "missing@example.com" },
    });
    fireEvent.click(screen.getByTestId("connection-grant-submit"));

    await waitFor(() => {
      expect(screen.getByText("No account for that email yet")).toBeInTheDocument();
    });
  });

  it("shows an error when revoke fails", async () => {
    const row = {
      id: "grant-9",
      connection_id: "conn-a",
      user_id: "u9",
      email: "viewer@example.com",
      role: "client_viewer",
      created_at: "2026-01-02T00:00:00Z",
    };
    mocks.listConnectionGrants.mockResolvedValue([row]);
    mocks.deleteConnectionGrant.mockRejectedValue(new Error("Grant not found"));

    render(<ConnectionTeamGrantsPanel connectionId="conn-a" />);

    await waitFor(() => {
      expect(screen.getByText("viewer@example.com")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("connection-grant-revoke-grant-9"));
    fireEvent.click(screen.getByTestId("connection-grant-revoke-confirm"));

    await waitFor(() => {
      expect(mocks.deleteConnectionGrant).toHaveBeenCalledWith("grant-9");
      expect(screen.getByTestId("error-notice")).toHaveTextContent("Grant not found");
    });
  });
});

/** @vitest-environment happy-dom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  api: {
    authStatus: vi.fn(),
    listApiKeys: vi.fn(),
    listAuditLogs: vi.fn(),
    accountOAuthIdentities: vi.fn(),
  },
  storedKey: null as string | null,
}));

vi.mock("@/components/settings/settings-operate.css", () => ({}));

vi.mock("@/lib/api", () => ({
  api: mocks.api,
  getStoredApiKey: () => mocks.storedKey,
  setStoredApiKey: vi.fn(),
}));

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: vi.fn(),
}));

import SettingsPage from "./page";

const AUTH_ON = {
  auth_mode: "api_key",
  auth_enabled: true,
  active_keys: 0,
  env_key_configured: false,
  bootstrap_available: false,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mocks.storedKey = null;
});

describe("settings page states", () => {
  it("shows status and audit skeletons while the API answers", () => {
    mocks.api.authStatus.mockReturnValue(new Promise(() => undefined));
    render(<SettingsPage />);

    expect(screen.getByTestId("settings-status-loading")).toHaveAttribute("role", "status");
    expect(screen.getByText("Loading API status.")).toBeInTheDocument();
    expect(screen.getByTestId("settings-audit-loading")).toHaveAttribute("role", "status");
    expect(screen.getByText("Loading the audit log.")).toBeInTheDocument();
    expect(screen.queryByText("No audit entries yet")).toBeNull();
    expect(screen.queryByText(/Loading…|Loading\.\.\./)).toBeNull();
    expect(screen.getByTestId("settings-honesty")).toBeInTheDocument();
    expect(screen.getByTestId("settings-stage-rail")).toBeInTheDocument();
  });

  it("shows key and audit empty states once both lists come back empty", async () => {
    mocks.storedKey = "oc_test";
    mocks.api.authStatus.mockResolvedValue(AUTH_ON);
    mocks.api.listApiKeys.mockResolvedValue([]);
    mocks.api.listAuditLogs.mockResolvedValue([]);
    render(<SettingsPage />);

    expect(await screen.findByRole("heading", { name: "No API keys yet" })).toBeInTheDocument();
    expect(
      screen.getByText("Keys you create appear here with their prefix and a Revoke button."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No audit entries yet" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Each POST, PUT, PATCH, or DELETE request to this API appears here with its status and duration.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("settings-audit-loading")).toBeNull();
    expect(screen.getByTestId("settings-create-key-btn")).toHaveTextContent("Create API key");
    expect(screen.getByTestId("settings-create-key-btn").className).toMatch(/bg-accent/);

    fireEvent.click(screen.getByRole("button", { name: "Name a key" }));
    expect(document.activeElement).toBe(screen.getByLabelText("Key name"));
  });

  it("does not claim there are no keys when keys are not listed for this browser", async () => {
    mocks.api.authStatus.mockResolvedValue(AUTH_ON);
    mocks.api.listAuditLogs.mockResolvedValue([]);
    render(<SettingsPage />);

    expect(await screen.findByRole("heading", { name: "No audit entries yet" })).toBeInTheDocument();
    expect(screen.queryByText("No API keys yet")).toBeNull();
  });

  it("shows bootstrap primary when bootstrap is available", async () => {
    mocks.api.authStatus.mockResolvedValue({ ...AUTH_ON, bootstrap_available: true });
    mocks.api.listAuditLogs.mockResolvedValue([]);
    render(<SettingsPage />);

    expect(await screen.findByTestId("settings-bootstrap-btn")).toHaveTextContent(
      "Generate first API key",
    );
    expect(screen.getByTestId("settings-bootstrap-btn").className).toMatch(/bg-accent/);
    expect(screen.queryByTestId("settings-create-key-btn")).toBeNull();
    expect(screen.getByTestId("settings-bootstrap-guide")).toBeInTheDocument();
  });
});

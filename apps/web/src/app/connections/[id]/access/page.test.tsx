/** @vitest-environment happy-dom */
import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AccessPage from "./page";

const mocks = vi.hoisted(() => ({
  getConnection: vi.fn(),
  listGroups: vi.fn(),
  listAccessRights: vi.fn(),
  listRecordRules: vi.fn(),
  listSnapshots: vi.fn(),
  getMultiCompanyGuidance: vi.fn(),
  getDocumentsGate: vi.fn(),
  getDocumentsFolderMap: vi.fn(),
  accessMatrix: vi.fn(),
  updateAccessRight: vi.fn(),
  createAccessRight: vi.fn(),
  probeConnection: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "conn-1" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/connections/conn-1/access",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
vi.mock("@/components/access/access-operate.css", () => ({}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }));
vi.mock("@/lib/use-sync-shell-context", () => ({ useSyncShellContext: () => undefined }));
vi.mock("@/components/VersionAwarenessBanner", () => ({ VersionAwarenessBanner: () => null }));
vi.mock("@/components/CapabilityProbePanel", () => ({ CapabilityProbePanel: () => null }));
vi.mock("@/components/expert/ExplainThisButton", () => ({
  ExplainThisButton: ({ label }: { label: string }) => <button type="button">{label}</button>,
}));
vi.mock("@/components/access/ConnectionTeamGrantsPanel", () => ({
  ConnectionTeamGrantsPanel: () => null,
}));
vi.mock("@/components/access/AccessExtras", () => ({ AccessExtras: () => null }));
vi.mock("@/components/access/AccessSnapshots", () => ({ AccessSnapshots: () => null }));
vi.mock("@/lib/api", () => {
  class ConfirmationRequiredError extends Error {
    risks: string[] = [];
    warning = "";
    confirm_phrase = "I understand the risks";
  }
  return { ConfirmationRequiredError, api: mocks };
});

const GROUPS = [
  { id: 2, name: "User", full_name: "Sales / User", share: false },
  { id: 3, name: "Administrator", full_name: "Sales / Administrator", share: false },
];

function seed(major: number, write_mode: "standard" | "production" = "standard") {
  mocks.getConnection.mockResolvedValue({
    id: "conn-1",
    name: "Lagos Sessions",
    url: "",
    db_name: "",
    username: "",
    server_version: `${major}.0`,
    write_mode,
    created_at: null,
    updated_at: null,
    capabilities: { major, ga: true },
  });
  mocks.listGroups.mockResolvedValue(GROUPS);
  mocks.listAccessRights.mockResolvedValue([
    {
      id: 21,
      name: "Partner user",
      model: "res.partner",
      model_id: 1,
      group_id: 2,
      group_name: "Sales / User",
      perm_read: true,
      perm_write: false,
      perm_create: false,
      perm_unlink: false,
      active: true,
    },
  ]);
  mocks.listRecordRules.mockResolvedValue([]);
  mocks.listSnapshots.mockResolvedValue([]);
  mocks.getMultiCompanyGuidance.mockResolvedValue({ title: "", body: "" });
  mocks.getDocumentsGate.mockResolvedValue({ available: false });
  mocks.getDocumentsFolderMap.mockResolvedValue({ mapping: {} });
  mocks.accessMatrix.mockResolvedValue({
    models: ["res.partner"],
    groups: GROUPS,
    cells: [
      {
        model: "res.partner",
        group_id: 2,
        access_id: 21,
        name: "Partner user",
        perm_read: true,
        perm_write: false,
        perm_create: false,
        perm_unlink: false,
        active: true,
      },
    ],
  });
  mocks.updateAccessRight.mockResolvedValue({});
  mocks.createAccessRight.mockResolvedValue({ id: 99, model: "res.partner" });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Access page (UI-S-19)", () => {
  it("Odoo 19: access + rules, matrix first, saves staged rights to Odoo", async () => {
    seed(19);
    render(<AccessPage />);
    expect(await screen.findByTestId("access-matrix-table")).toBeInTheDocument();
    expect(screen.getAllByTestId("access-version-model").map((n) => n.textContent)).toEqual([
      "ir.model.access",
      "ir.rule",
    ]);
    expect(screen.getByTestId("access-tab-rules")).toBeInTheDocument();
    expect(mocks.listRecordRules).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Write on res.partner for Sales / User" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Read on res.partner for Sales / Administrator" }),
    );
    fireEvent.click(screen.getByTestId("access-matrix-save"));

    await waitFor(() =>
      expect(mocks.updateAccessRight).toHaveBeenCalledWith("conn-1", 21, { perm_write: true }),
    );
    expect(mocks.createAccessRight).toHaveBeenCalledWith(
      "conn-1",
      expect.objectContaining({
        model: "res.partner",
        group_id: 3,
        perm_read: true,
        perm_unlink: false,
      }),
    );
    expect(await screen.findByTestId("access-notice")).toHaveTextContent("Saved 2 rights to Odoo");
    expect(mocks.accessMatrix.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("Odoo 20: one ir.access matrix, no record rules tab, no ir.rule read", async () => {
    seed(20);
    render(<AccessPage />);
    expect(await screen.findByTestId("access-matrix-table")).toBeInTheDocument();
    expect(screen.getAllByTestId("access-version-model").map((n) => n.textContent)).toEqual([
      "ir.access",
    ]);
    expect(screen.getByTestId("odoo20-access-note")).toBeInTheDocument();
    expect(screen.getByTestId("access-matrix-title")).toHaveTextContent("ir.access matrix");
    expect(screen.queryByTestId("access-tab-rules")).toBeNull();
    expect(mocks.listRecordRules).not.toHaveBeenCalled();
  });

  it("production: R3 links to the plan card and never applies inline", async () => {
    seed(19, "production");
    render(<AccessPage />);
    expect(await screen.findByTestId("access-plan-link")).toHaveAttribute(
      "href",
      "/approvals?connection_id=conn-1",
    );
    expect(screen.queryByTestId("access-matrix-save")).toBeNull();
    expect(screen.getByTestId("access-gate-title")).toHaveTextContent("plan card");
    expect(
      screen.getByRole("button", { name: "Write on res.partner for Sales / User" }),
    ).toBeDisabled();

    fireEvent.click(screen.getByTestId("access-tab-lines"));
    expect(await screen.findByTestId("access-create-plan-link")).toHaveAttribute(
      "href",
      "/approvals?connection_id=conn-1",
    );
    expect(screen.queryByTestId("access-create")).toBeNull();
    expect(mocks.updateAccessRight).not.toHaveBeenCalled();
    expect(mocks.createAccessRight).not.toHaveBeenCalled();
  });

  it("load failure shows what / why / next with a retry", async () => {
    seed(19);
    mocks.listAccessRights.mockRejectedValueOnce(new Error("AccessError: not allowed to read"));
    render(<AccessPage />);
    expect(await screen.findByTestId("access-error-title")).toHaveTextContent(
      "Odoo refused to show access rights",
    );
    expect(screen.getByTestId("access-error-next")).toHaveTextContent("admin");
    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("access-error-retry"));
    await waitFor(() => expect(screen.queryByTestId("access-error")).toBeNull());
  });
});

/** @vitest-environment happy-dom */
import type { ReactNode } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ReportsPage from "./page";

const mocks = vi.hoisted(() => ({
  getConnection: vi.fn(),
  listReports: vi.fn(),
  listPaperformats: vi.fn(),
  createReport: vi.fn(),
  updateReport: vi.fn(),
  deleteReport: vi.fn(),
  mergePrintReports: vi.fn(),
  reportRenderProbe: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "conn-1" }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api", () => ({
  api: mocks,
}));

vi.mock("@/components/reports/ReportDesigner", () => ({
  ReportDesigner: () => <div data-testid="report-designer-stub">designer</div>,
}));

function readyConnection(reports: unknown[] = []) {
  mocks.getConnection.mockResolvedValue({
    id: "conn-1",
    name: "Dev",
    write_mode: "standard",
    server_version: "19.0",
    capabilities: {
      major: 19,
      edition: "community",
      server_version: "19.0",
      supported: ["list_as_list_type"],
      unsupported: [],
      ga: true,
      message: "ok",
    },
  });
  mocks.listReports.mockResolvedValue(reports);
  mocks.listPaperformats.mockResolvedValue([{ id: 1, name: "A4" }]);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Reports page PDF-06 composition", () => {
  it("shows kit EmptyState when the report list is empty", async () => {
    readyConnection([]);
    render(<ReportsPage />);
    expect(await screen.findByTestId("reports-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByTestId("reports-list-loading")).not.toBeInTheDocument();
    });
    expect(screen.getByText("No custom reports yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open create form" })).toBeInTheDocument();
  });

  it("uses Skeleton while the report list hydrates", async () => {
    let resolveReports: (v: unknown) => void = () => {};
    mocks.getConnection.mockResolvedValue({
      id: "conn-1",
      name: "Dev",
      write_mode: "standard",
      server_version: "19.0",
      capabilities: {
        major: 19,
        ga: true,
        supported: ["list_as_list_type"],
        unsupported: [],
        edition: "community",
        server_version: "19.0",
        message: "ok",
      },
    });
    mocks.listPaperformats.mockResolvedValue([]);
    mocks.listReports.mockReturnValue(
      new Promise((resolve) => {
        resolveReports = resolve;
      }),
    );
    render(<ReportsPage />);
    expect(await screen.findByTestId("reports-list-loading")).toBeInTheDocument();
    resolveReports([]);
    await waitFor(() => {
      expect(screen.queryByTestId("reports-list-loading")).not.toBeInTheDocument();
    });
  });

  it("primary persist label is exactly Save the printout", async () => {
    readyConnection([
      {
        id: 7,
        name: "Partner sheet",
        model: "res.partner",
        report_name: "custom.report_partner",
        paperformat_name: "A4",
        arch: "<t/>",
      },
    ]);
    render(<ReportsPage />);
    await screen.findByText("Partner sheet");
    // Click list item to select, then code-tab save chrome always mounts the primary CTA.
    screen.getByText("Partner sheet").click();
    const save = await screen.findByTestId("reports-save-arch");
    expect(save).toHaveTextContent("Save the printout");
  });
});

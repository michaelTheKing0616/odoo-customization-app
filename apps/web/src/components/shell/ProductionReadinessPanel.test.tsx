import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProductionReadinessPanel } from "./ProductionReadinessPanel";

vi.mock("@/lib/api", () => ({
  api: {
    getProductionReadiness: vi.fn(async () => ({
      passed: false,
      items: [
        {
          key: "snapshot_restore_drill",
          label: "Snapshot + restore drill",
          status: "todo",
          detail: "Run the snapshot drill",
        },
      ],
      drill_snapshot_id: null,
      updated_at: null,
      first_write_acknowledged: false,
    })),
    runProductionSnapshotDrill: vi.fn(),
    confirmProductionLeastPrivilege: vi.fn(),
    verifyProductionBackupArtifact: vi.fn(),
  },
}));

describe("ProductionReadinessPanel", () => {
  it("uses calm collapsed checklist for Online when write mode is not production", async () => {
    render(
      <ProductionReadinessPanel
        connection={{
          id: "c1",
          name: "Online",
          url: "https://experiment-company.odoo.com",
          db_name: "experiment-company",
          username: "admin",
          server_version: "saas~19.4+e",
          write_mode: "standard",
          created_at: null,
          updated_at: null,
        }}
      />,
    );
    expect(
      await screen.findByText(/optional until production write mode/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("production-readiness-disclosure")).toBeInTheDocument();
  });
});

/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StudioHonestyBanners } from "./StudioHonestyBanners";

afterEach(() => cleanup());

const base = {
  connectionId: "c1",
  applyNote: null as string | null,
  calloutTitle: "Applied to Odoo",
  odooAppUrl: null as string | null,
  artifactConsistent: true,
  appIsLiveOnOdoo: false,
  stockReuse: false,
  refuseClone: false,
  goldOptionA: false,
  authoredOptionA: false,
  fieldPack: false,
  hostFormName: "Vendor bill",
  liveAppName: "Helpdesk",
  grammarCard: null,
  surfaceFindings: [] as { detail?: string }[],
  liveApplyBanner: null,
  unfinishedBanner: null,
  operatorSurface: null,
  placementRows: [] as { name: string; string: string; slot: string }[],
  slotCatalog: [] as { id: string; label: string; phrase: string }[],
  stockApps: [] as { id: string; label: string }[],
  applyBlocked: null as string | null,
  refineBusy: false,
  onPlaceField: vi.fn(),
};

describe("StudioHonestyBanners", () => {
  it("keeps preview-only honesty and surface-gate install block", () => {
    render(
      <StudioHonestyBanners
        {...base}
        liveAppName="Helpdesk"
        grammarCard={{
          shape: "workspace",
          display_name: "Helpdesk",
          header_model: "x_ticket",
          document_count: 1,
          slots: [],
          states: [],
          extra_apps: 0,
          summary: "One Helpdesk document with tickets.",
        }}
        surfaceFindings={[{ detail: "surface: duplicate notebook" }]}
        operatorSurface={{
          host_buttons: [],
          residual_buttons: [],
          stock_links: [],
          summary: "Open Helpdesk from the home grid.",
        }}
      />,
    );
    expect(screen.getByText("Preview only — not in Odoo yet").parentElement?.textContent).toMatch(
      /Tickets is a submenu/,
    );
    expect(screen.getByTestId("studio-grammar-card").textContent).toMatch(/Helpdesk document/);
    expect(screen.getByTestId("studio-surface-gate").textContent).toMatch(/Not ready to install/);
    expect(screen.getByTestId("studio-operator-surface").textContent).toMatch(/home grid/);
  });

  it("places inherit fields via refine phrases", () => {
    const onPlaceField = vi.fn();
    render(
      <StudioHonestyBanners
        {...base}
        fieldPack
        hostFormName="Vendor bill"
        placementRows={[{ name: "x_tin", string: "Vendor TIN", slot: "next_to_dates" }]}
        slotCatalog={[
          { id: "next_to_dates", label: "Next to dates", phrase: "next to dates" },
          { id: "next_to_vendor", label: "Next to vendor", phrase: "next to vendor" },
        ]}
        onPlaceField={onPlaceField}
      />,
    );
    fireEvent.change(screen.getByLabelText("Place Vendor TIN"), {
      target: { value: "next_to_vendor" },
    });
    expect(onPlaceField).toHaveBeenCalledWith("Vendor TIN", "next to vendor");
  });
});

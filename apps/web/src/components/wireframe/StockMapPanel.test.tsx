import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
const wireframeMap = vi.fn();
vi.mock("@/lib/api", () => ({ api: { wireframeMap: (...a: unknown[]) => wireframeMap(...a) } }));

import { StockMapPanel, briefFromMap } from "./StockMapPanel";
import type { WireframeMap } from "@/lib/api/wireframe";

const MAP: WireframeMap = {
  target: { action: "new", model: "x_vehicle_inspection", name: "Vehicle inspection", score: 0, maybe: { model: "fleet.vehicle", name: "Vehicle" } },
  rows: [
    { region: "r1", label: "Plate number", hint: "char", action: "new", field: null, type: "char" },
    { region: "r2", label: "Email", hint: "email", action: "reuse", field: "email", field_label: "Email", type: "char" },
  ],
  questions: [{ id: "model", text: "Is it Vehicle?", options: [{ id: "extend", label: "Yes, add to Vehicle" }, { id: "new", label: "No" }] }],
  summary: "1 of 2 boxes use fields Odoo already has; 1 would be new.",
  install: { mode: "module", why: "This database can install a custom module." },
  hosting: "self_hosted",
  guards: { redacted: {}, flagged_regions: [] },
};

describe("Q6 StockMapPanel", () => {
  it("brief prefers stock: extends the stock model when the person says so", () => {
    const b = briefFromMap(MAP, { model: "extend" });
    expect(b).toMatch(/Add to Odoo’s Vehicle \(fleet\.vehicle\)/);
    expect(b).toMatch(/Use the fields Odoo already has: Email → Email/);
    expect(b).toMatch(/Add new fields: Plate number \(char\)/);
  });

  it("asks at most the open questions, then hands the brief to App Studio", async () => {
    wireframeMap.mockResolvedValue(MAP);
    render(<StockMapPanel connectionId="c1" sketch={{ title: "x" }} imageUrl={null} onBuild={push} />);
    await waitFor(() => expect(screen.getByTestId("wireframe-map-summary")).toBeInTheDocument());
    expect(screen.getByTestId("wireframe-map-build")).toBeDisabled();
    fireEvent.click(screen.getByText("Yes, add to Vehicle"));
    fireEvent.click(screen.getByTestId("wireframe-map-build"));
    expect(sessionStorage.getItem("app-studio-prompt:c1")).toMatch(/fleet\.vehicle/);
    expect(push).toHaveBeenCalledWith("/connections/c1/studio");
  });

  it("outlines each box on the sketch and strengthens the hovered one", async () => {
    wireframeMap.mockResolvedValue({ ...MAP, rows: [{ ...MAP.rows[0], box: [0.1, 0.2, 0.5, 0.1] }, MAP.rows[1]] });
    render(<StockMapPanel connectionId="c1" sketch={{ title: "x" }} imageUrl="blob:x" onBuild={push} />);
    const box = await screen.findByTestId("wireframe-box-r1");
    expect(box.style.left).toBe("10%");
    expect(screen.queryByTestId("wireframe-box-r2")).toBeNull();
    fireEvent.mouseEnter(screen.getAllByText("Plate number").at(-1)!.closest("tr")!);
    expect(box.className).toMatch(/border-2/);
  });
});

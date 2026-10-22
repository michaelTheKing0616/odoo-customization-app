/** @vitest-environment happy-dom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Connection } from "@/lib/api";
import { ODOO20_COMBINED_ACCESS_NOTE } from "@/lib/accessMajor";
import { accessVersionFrame, accessWriteGate } from "@/lib/accessScreen";
import { AccessStateGuide } from "./AccessStateGuide";
import { AccessVersionStrip } from "./AccessVersionStrip";
import { AccessWorkspaceTabs } from "./AccessWorkspaceTabs";

afterEach(() => cleanup());

function conn(major: number, write_mode: Connection["write_mode"] = "standard"): Connection {
  return {
    id: "c1",
    name: "Dev",
    url: "",
    db_name: "",
    username: "",
    server_version: `${major}.0`,
    write_mode,
    created_at: null,
    updated_at: null,
    capabilities: { major, ga: true } as Connection["capabilities"],
  };
}

describe("AccessVersionStrip", () => {
  it("Odoo 20 names ir.access only and carries the combined note", () => {
    render(
      <AccessVersionStrip frame={accessVersionFrame(20)} gate={accessWriteGate(conn(20), "c1")} />,
    );
    const models = screen.getAllByTestId("access-version-model").map((n) => n.textContent);
    expect(models).toEqual(["ir.access"]);
    expect(screen.getByTestId("odoo20-access-note")).toHaveTextContent(ODOO20_COMBINED_ACCESS_NOTE);
    expect(screen.getByTestId("access-version-label")).toHaveTextContent("Odoo 20");
  });

  it("Odoo 19 names ir.model.access plus ir.rule and no Odoo 20 note", () => {
    render(
      <AccessVersionStrip frame={accessVersionFrame(19)} gate={accessWriteGate(conn(19), "c1")} />,
    );
    const models = screen.getAllByTestId("access-version-model").map((n) => n.textContent);
    expect(models).toEqual(["ir.model.access", "ir.rule"]);
    expect(screen.queryByTestId("odoo20-access-note")).toBeNull();
  });

  it("gate chip says whether a save goes to Odoo or to approval", () => {
    render(
      <AccessVersionStrip
        frame={accessVersionFrame(19)}
        gate={accessWriteGate(conn(19, "production"), "c1")}
      />,
    );
    const chip = screen.getByTestId("access-gate-chip");
    expect(chip).toHaveTextContent("Needs approval");
    expect(chip).toHaveAttribute("data-mode", "plan");
  });
});

describe("AccessStateGuide", () => {
  it("renders what / why / next and announces errors", () => {
    render(
      <AccessStateGuide
        guide={{ title: "T", why: "W", next: "N" }}
        tone="danger"
        live
        testId="g"
      />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByTestId("g-title")).toHaveTextContent("T");
    expect(screen.getByTestId("g-why")).toHaveTextContent("W");
    expect(screen.getByTestId("g-next")).toHaveTextContent("N");
  });

  it("empty states do not announce", () => {
    render(<AccessStateGuide guide={{ title: "T", why: "W", next: "N" }} testId="g" />);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("AccessWorkspaceTabs", () => {
  it("Odoo 20 has no record rules tab; 19 does", () => {
    const { unmount } = render(
      <AccessWorkspaceTabs tabs={accessVersionFrame(20).tabs} value="matrix" onChange={vi.fn()}>
        <p>panel</p>
      </AccessWorkspaceTabs>,
    );
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Matrix",
      "Access lines",
    ]);
    unmount();
    render(
      <AccessWorkspaceTabs tabs={accessVersionFrame(19).tabs} value="matrix" onChange={vi.fn()}>
        <p>panel</p>
      </AccessWorkspaceTabs>,
    );
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Matrix",
      "Access lines",
      "Record rules",
    ]);
  });

  it("tabpanel is labelled by the selected tab and arrows change tab", () => {
    const onChange = vi.fn();
    render(
      <AccessWorkspaceTabs
        tabs={["matrix", "lines", "rules"]}
        value="matrix"
        onChange={onChange}
        counts={{ lines: 4 }}
      >
        <p>panel</p>
      </AccessWorkspaceTabs>,
    );
    const selected = screen.getByRole("tab", { selected: true });
    expect(selected).toHaveTextContent("Matrix");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "access-tab-matrix");
    expect(screen.getByTestId("access-tab-lines")).toHaveTextContent("4");
    fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("lines");
    fireEvent.keyDown(screen.getByRole("tablist"), { key: "End" });
    expect(onChange).toHaveBeenLastCalledWith("rules");
  });
});

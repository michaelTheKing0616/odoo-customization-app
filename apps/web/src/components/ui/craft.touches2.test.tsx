import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { HealthArch, Sparkline, WithTable, voussoirOrder } from "./craft";

describe("Q2 touches 5/6/62/63", () => {
  it("fills from both legs; keystone last", () => {
    expect(voussoirOrder(5)).toEqual([0, 4, 1, 3, 2]);
  });
  it("names weak areas", () => {
    render(<HealthArch score={70} parts={[{ key: "a", label: "Layout", score: 90 }, { key: "b", label: "Speed", score: 40 }]} />);
    expect(screen.getByTestId("health-arch").getAttribute("aria-label")).toContain("Weak: Speed");
  });
  it("ghost chart before data", () => {
    render(<Sparkline values={[0, 0, 0]} label="Moved" ghost="Fills in later" />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toContain("Fills in later");
  });
  it("chart switches to a table", () => {
    render(<WithTable label="t" rows={[["5 min ago", 3]]}><span>chart</span></WithTable>);
    fireEvent.click(screen.getByTestId("chart-table-toggle"));
    expect(screen.getByText("5 min ago")).toBeTruthy();
  });
});

import { coachShortcut, goToKeysFor } from "./craft";
describe("83 shortcut coaching", () => {
  it("tips once, on the third click", () => {
    localStorage.removeItem("ingenium.shortcutCoach");
    const seen: string[] = [];
    const n = (m: string) => seen.push(m);
    expect([coachShortcut("G B", n), coachShortcut("G B", n), coachShortcut("G B", n), coachShortcut("G B", n)]).toEqual([false, false, true, false]);
    expect(seen).toEqual(["Tip: press G then B"]);
    expect(goToKeysFor("/bridge")).toBe("G B");
  });
});

import { seasonalArch } from "./craft";
describe("150 seasonal arches", () => {
  it("only on 1 October and 12 June, Lagos time", () => {
    expect(seasonalArch(new Date("2026-10-01T09:00:00Z"))).toBe("independence");
    expect(seasonalArch(new Date("2026-09-30T23:30:00Z"))).toBe("independence");
    expect(seasonalArch(new Date("2026-06-12T12:00:00Z"))).toBe("democracy");
    expect(seasonalArch(new Date("2026-10-20T12:00:00Z"))).toBeNull();
  });
});

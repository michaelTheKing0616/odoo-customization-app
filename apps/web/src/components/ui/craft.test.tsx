import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import { Dumbbell, EditInPlace, ScrubNumber, Money, RollingNumber, Sparkline, relativeLabel } from "./craft";

describe("craft", () => {
  it("relative labels keep number and unit together", () => {
    const now = Date.now();
    expect(relativeLabel(now - 10_000, now)).toBe("just now");
    expect(relativeLabel(now - 4 * 60_000, now)).toBe("4\u00a0min ago");
  });
  it("money mutes decimals", () => {
    const { container } = render(<Money amount={1250} />);
    expect([...container.querySelectorAll(".money-dec")].map((n) => n.textContent).join("")).toBe(".00");
  });
  it("rolling number keeps plain text", () => {
    const { container } = render(<RollingNumber value={12345} />);
    expect(container.textContent).toBe("12,345");
  });
  it("sparkline labels the latest value and needs two points", () => {
    expect(render(<Sparkline values={[1]} label="Syncs" />).container.innerHTML).toBe("");
    const { container } = render(<Sparkline values={[1, 3, 2]} label="Syncs" />);
    expect(container.querySelector("svg")?.getAttribute("aria-label")).toBe("Syncs: latest 2");
  });
  it("dumbbell reads before to after", () => {
    const el = render(<Dumbbell before={10} after={4} max={10} label="Open leads" />).container.querySelector(".dumbbell");
    expect(el?.getAttribute("aria-label")).toBe("Open leads: 10 to 4");
    expect(el?.getAttribute("data-dir")).toBe("down");
  });
  it("edit in place: Enter saves, Escape reverts", () => {
    const save = vi.fn();
    const { container } = render(<EditInPlace value="Leads" label="Menu name" onSave={save} />);
    fireEvent.click(container.querySelector("button")!);
    const input = container.querySelector("input")!;
    fireEvent.change(input, { target: { value: "Prospects" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(save).not.toHaveBeenCalled();
    fireEvent.click(container.querySelector("button")!);
    fireEvent.change(container.querySelector("input")!, { target: { value: "Prospects" } });
    fireEvent.keyDown(container.querySelector("input")!, { key: "Enter" });
    expect(save).toHaveBeenCalledWith("Prospects");
  });
  it("scrub number: arrows step, shift steps 10, clamps", () => {
    const change = vi.fn();
    const { container } = render(<ScrubNumber value={5} min={0} max={12} label="Columns" onChange={change} />);
    const el = container.querySelector("[role=spinbutton]")!;
    fireEvent.keyDown(el, { key: "ArrowUp" });
    fireEvent.keyDown(el, { key: "ArrowUp", shiftKey: true });
    fireEvent.keyDown(el, { key: "ArrowDown", shiftKey: true });
    expect(change.mock.calls.map((c) => c[0])).toEqual([6, 12, 0]);
  });
});

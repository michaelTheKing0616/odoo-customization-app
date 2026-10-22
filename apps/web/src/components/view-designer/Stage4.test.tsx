import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ updateConnectionWriteMode: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { updateConnectionWriteMode: (...a: unknown[]) => m.updateConnectionWriteMode(...a) } }));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

import { WriteModeNote } from "./WriteModeNote";
import { PublishMoment } from "./PublishMoment";
import { clearWriteRefusal, isObserverRefusal, noteWriteRefusal } from "./writeModeSignal";
import { isNetworkError, messageOf } from "./useViewDesigner";
import { CompareView } from "./Builder2d";

afterEach(() => {
  cleanup();
  clearWriteRefusal();
  window.localStorage.clear();
});

describe("stage 4", () => {
  it("shows 'Switch to write mode' only after an Observer refusal, and switches through the typed confirm", async () => {
    render(<WriteModeNote connectionId="c1" />);
    expect(screen.queryByTestId("vd-write-mode")).toBeNull();
    noteWriteRefusal(new Error("boom"));
    expect(screen.queryByTestId("vd-write-mode")).toBeNull();
    const refusal = Object.assign(new Error("read-only"), { detail: { error: "observer_mode", message: "read-only" } });
    expect(isObserverRefusal(refusal)).toBe(true);
    act(() => void messageOf(refusal));
    fireEvent.click(await screen.findByTestId("vd-write-mode-switch"));
    expect(m.updateConnectionWriteMode).not.toHaveBeenCalled();
    m.updateConnectionWriteMode.mockResolvedValue({ id: "c1", write_mode: "standard" });
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "I understand the risks" } });
    fireEvent.click(screen.getByRole("button", { name: /confirm|continue|proceed/i }));
    await waitFor(() => expect(m.updateConnectionWriteMode).toHaveBeenCalledWith("c1", "standard"));
    await waitFor(() => expect(screen.queryByTestId("vd-write-mode")).toBeNull());
  });

  it("marks the first publish once per connection", () => {
    const { rerender } = render(<PublishMoment connectionId="c1" count={0} />);
    expect(screen.queryByTestId("vd-publish-moment")).toBeNull();
    rerender(<PublishMoment connectionId="c1" count={1} />);
    expect(screen.getByTestId("vd-publish-moment")).toHaveTextContent("Your first change is live.");
    cleanup();
    const again = render(<PublishMoment connectionId="c1" count={0} />);
    again.rerender(<PublishMoment connectionId="c1" count={1} />);
    expect(screen.queryByTestId("vd-publish-moment")).toBeNull();
  });

  it("tells a dropped connection apart from a refusal", () => {
    expect(isNetworkError(new TypeError("Failed to fetch"))).toBe(true);
    expect(isNetworkError(Object.assign(new Error("Not allowed"), { status: 403 }))).toBe(false);
  });

  it("steps through each remaining difference and points at it", () => {
    const item = (node: string, label: string) => ({ node, tag: "field", label, hidden: false });
    render(<CompareView cmp={{
      source: { major: 17, items: [item("s1", "Activities")] }, target_now: { major: 19, items: [] }, target_after: { items: [item("t1", "Warehouse")] },
      changes: [], problems: [], replaces: false, note: "",
      still_different: [{ kind: "added", node: "t1", text: "Only there: Warehouse" }, { kind: "removed", node: "s1", text: "Not there: Activities" }],
    } as never} />);
    fireEvent.click(screen.getByTestId("vd2e-diff-open"));
    expect(screen.getByTestId("vd2e-diff-step")).toHaveTextContent("Difference 1 of 2: Only there, Warehouse");
    expect(screen.getByText("Warehouse").closest("li")).toHaveAttribute("aria-current", "true");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByTestId("vd2e-diff-step")).toHaveTextContent("Difference 2 of 2: Only here, Activities");
    expect(screen.getByText("Activities").closest("li")).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});

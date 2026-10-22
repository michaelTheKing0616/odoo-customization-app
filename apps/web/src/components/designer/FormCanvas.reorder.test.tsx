import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { FormCanvas } from "./FormCanvas";

afterEach(() => cleanup());

const GROUPS = [
  {
    id: "g1",
    string: "Identity",
    fields: [
      { id: "f1", name: "x_name", string: "Subject" },
      { id: "f2", name: "x_code", string: "Code" },
    ],
  },
];

describe("FormCanvas reorder affordances (UI-S-12)", () => {
  it("marks rows reorderable only when pointer reorder is wired", () => {
    const { rerender } = render(<FormCanvas title="Ticket" groups={GROUPS} showChatter={false} />);
    expect(screen.getByTestId("canvas-field-x_name")).not.toHaveAttribute("data-reorderable");

    rerender(
      <FormCanvas title="Ticket" groups={GROUPS} showChatter={false} onReorderField={() => undefined} />,
    );
    expect(screen.getByTestId("canvas-field-x_name")).toHaveAttribute("data-reorderable");
  });

  it("steps a row with arrow keys through the ReorderableBlocks stack", () => {
    const onReorderField = vi.fn();
    render(
      <FormCanvas title="Ticket" groups={GROUPS} showChatter={false} onReorderField={onReorderField} />,
    );
    fireEvent.keyDown(screen.getByTestId("canvas-field-x_name"), { key: "ArrowDown" });
    expect(onReorderField).toHaveBeenCalledWith("f1", "g1", 1);
  });

  it("shows one insertion line while a palette field hovers the list", () => {
    const { container } = render(
      <FormCanvas title="Ticket" groups={GROUPS} showChatter={false} onDropFieldName={() => undefined} />,
    );
    const list = screen.getByTestId("canvas-drop-list");
    expect(container.querySelectorAll(".designer-drop-line")).toHaveLength(0);
    fireEvent.dragOver(list, { dataTransfer: { types: ["text/odoo-field"] } });
    expect(list.className).toContain("is-over");
    expect(container.querySelectorAll(".designer-drop-line")).toHaveLength(1);
  });

  it("keeps the empty group drop hint", () => {
    render(
      <FormCanvas
        title="Ticket"
        groups={[{ id: "g1", string: "Empty", fields: [] }]}
        showChatter={false}
      />,
    );
    expect(screen.getByText("Drop a field here")).toBeInTheDocument();
  });
});

describe("FormCanvas grip (UI-S-12)", () => {
  it("renders a non-button grip per row only when reorder is wired", () => {
    const { rerender } = render(<FormCanvas title="Ticket" groups={GROUPS} showChatter={false} />);
    expect(screen.queryAllByTestId("canvas-grip")).toHaveLength(0);
    rerender(
      <FormCanvas title="Ticket" groups={GROUPS} showChatter={false} onReorderField={() => undefined} />,
    );
    const grips = screen.getAllByTestId("canvas-grip");
    expect(grips).toHaveLength(2);
    grips.forEach((g) => {
      expect(g.tagName).toBe("SPAN");
      expect(g).toHaveAttribute("aria-hidden");
      expect(g.closest("button")).toBeNull();
    });
  });
});

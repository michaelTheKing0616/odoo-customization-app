import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FieldPalette } from "./FieldPalette";

describe("FieldPalette", () => {
  it("filters fields and starts a palette drag", () => {
    const onDragStart = vi.fn();
    render(
      <FieldPalette
        fields={[
          { name: "x_name", ttype: "char", label: "Name" },
          { name: "x_amount", ttype: "float", label: "Amount" },
        ]}
        onDragStart={onDragStart}
      />,
    );
    fireEvent.change(screen.getByLabelText("Filter fields"), { target: { value: "amount" } });
    expect(screen.getByTestId("palette-field-x_amount")).toBeTruthy();
    expect(screen.queryByTestId("palette-field-x_name")).toBeNull();

    const dt = {
      setData: vi.fn(),
      setDragImage: vi.fn(),
      effectAllowed: "none",
    };
    fireEvent.dragStart(screen.getByTestId("palette-field-x_amount"), { dataTransfer: dt });
    expect(onDragStart).toHaveBeenCalledWith("x_amount");
    expect(dt.setData).toHaveBeenCalledWith("text/odoo-field", "x_amount");
  });
});

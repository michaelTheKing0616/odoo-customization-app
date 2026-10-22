import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { KanbanCardPreview } from "./KanbanCardPreview";

afterEach(() => cleanup());

const FIELDS = [
  { id: "k1", name: "x_name", string: "Name" },
  { id: "k2", name: "x_partner_id", string: "Customer" },
  { id: "k3", name: "x_amount", string: "Amount" },
];

describe("KanbanCardPreview (UI-S-12)", () => {
  it("shows the group-by chip and one lane per sample column", () => {
    render(<KanbanCardPreview title="Ticket" groupBy="x_stage" fields={FIELDS} />);
    expect(screen.getByTestId("kanban-groupby-chip")).toHaveTextContent("x_stage");
    expect(screen.getByText("Column A")).toBeInTheDocument();
    expect(screen.getByText("Column B")).toBeInTheDocument();
  });

  it("falls back to a single lane and a Not grouped chip", () => {
    render(<KanbanCardPreview title="Ticket" groupBy={null} fields={FIELDS} />);
    expect(screen.queryByTestId("kanban-groupby-chip")).toBeNull();
    expect(screen.getByText("Not grouped")).toBeInTheDocument();
    expect(screen.getByText("All records")).toBeInTheDocument();
  });

  it("keeps step controls labelled and wired, with edges disabled", () => {
    const onMove = vi.fn();
    const onRemove = vi.fn();
    render(
      <KanbanCardPreview
        title="Ticket"
        groupBy={null}
        fields={FIELDS}
        onMoveField={onMove}
        onRemoveField={onRemove}
      />,
    );
    expect(screen.getByRole("button", { name: "Move x_name up" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move x_amount down" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Move x_partner_id down" }));
    expect(onMove).toHaveBeenCalledWith("k2", 1);
    fireEvent.click(screen.getByRole("button", { name: "Remove x_amount" }));
    expect(onRemove).toHaveBeenCalledWith("k3");
  });

  it("marks reorderable rows and moves with arrow keys", () => {
    const onMove = vi.fn();
    const { container } = render(
      <KanbanCardPreview title="Ticket" groupBy={null} fields={FIELDS} onMoveField={onMove} />,
    );
    const rows = container.querySelectorAll<HTMLElement>(".designer-kanban-field");
    expect(rows).toHaveLength(3);
    rows.forEach((row) => expect(row).toHaveAttribute("data-reorderable"));
    fireEvent.keyDown(rows[0], { key: "ArrowDown" });
    expect(onMove).toHaveBeenCalledWith("k1", 1);
  });

  it("highlights the selected field with the canvas selection class, not the brand tint", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <KanbanCardPreview
        title="Ticket"
        groupBy={null}
        fields={FIELDS}
        selectedFieldId="k2"
        onSelectField={onSelect}
      />,
    );
    const selected = container.querySelector(".designer-kanban-field.is-selected");
    expect(selected).not.toBeNull();
    expect(within(selected as HTMLElement).getByText("Customer")).toBeInTheDocument();
    expect(container.innerHTML).not.toContain("brand-subtle");
    fireEvent.click(screen.getByText("Amount"));
    expect(onSelect).toHaveBeenCalledWith("k3");
  });

  it("reads dropped palette fields from the drag payload", () => {
    const onDrop = vi.fn();
    render(
      <KanbanCardPreview title="Ticket" groupBy={null} fields={[]} onDropFieldName={onDrop} />,
    );
    const empty = screen.getByText("Drop fields here to build the card");
    fireEvent.drop(empty, {
      dataTransfer: { getData: (type: string) => (type === "text/odoo-field" ? "x_stage" : "") },
    });
    expect(onDrop).toHaveBeenCalledWith("x_stage");
  });
});

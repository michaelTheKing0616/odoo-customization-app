import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { FormCanvas } from "./FormCanvas";
import { ODOO_FIELD_MIME } from "@/lib/designer-dnd";

afterEach(() => cleanup());

describe("FormCanvas designer DnD surface", () => {
  it("renders statusbar stages, two-column groups, and notebook tab switch", () => {
    render(
      <FormCanvas
        title="Ticket"
        statusbar="x_status"
        statusbarVisible="new,in_progress,done"
        groupLayout="two-column"
        headerButtons={[{ id: "c", string: "Confirm", variant: "primary" }]}
        smartButtons={[{ id: "s", string: "Tasks", count: 4 }]}
        groups={[
          {
            id: "g1",
            string: "Identity",
            fields: [{ id: "f1", name: "x_name", string: "Subject", ttype: "char" }],
          },
          {
            id: "g2",
            string: "Details",
            fields: [{ id: "f2", name: "x_priority", string: "Priority", ttype: "selection" }],
          },
        ]}
        notebooks={[
          {
            id: "nb1",
            pages: [
              {
                id: "p1",
                string: "Lines",
                fields: [{ id: "lf1", name: "x_qty", string: "Qty", ttype: "integer" }],
              },
              {
                id: "p2",
                string: "Notes",
                fields: [{ id: "nf1", name: "x_notes", string: "Notes", ttype: "text" }],
              },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByTestId("form-canvas")).toBeTruthy();
    expect(screen.getByTestId("odoo-statusbar")).toBeTruthy();
    expect(screen.getByText("new")).toBeTruthy();
    expect(screen.getByText("Confirm")).toBeTruthy();
    expect(screen.getByTestId("odoo-button-box")).toBeTruthy();
    expect(screen.getByTestId("odoo-field-x_qty")).toBeTruthy();
    expect(screen.getByTestId("odoo-widget-char-x_name")).toBeTruthy();
    expect(screen.queryByTestId("odoo-field-x_notes")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Notes" }));
    expect(screen.getByTestId("odoo-field-x_notes")).toBeTruthy();
    expect(screen.queryByTestId("odoo-field-x_qty")).toBeNull();
  });

  it("keeps keyboard reorder callback contract", () => {
    const moves: Array<{ id: string; dir: -1 | 1 }> = [];
    render(
      <FormCanvas
        title="Ticket"
        groups={[
          {
            id: "g1",
            string: "Identity",
            fields: [
              { id: "f1", name: "x_name", string: "Subject" },
              { id: "f2", name: "x_code", string: "Code" },
            ],
          },
        ]}
        selectedFieldId="f1"
        onMoveField={(id, dir) => moves.push({ id, dir })}
        showChatter={false}
      />,
    );
    fireEvent.keyDown(window, { key: "ArrowDown" });
    expect(moves).toEqual([{ id: "f1", dir: 1 }]);
  });

  it("drops a palette field onto a group", () => {
    const dropped: Array<{ groupId: string; name: string; index?: number }> = [];
    render(
      <FormCanvas
        title="Ticket"
        groups={[
          {
            id: "g1",
            string: "Identity",
            fields: [{ id: "f1", name: "x_name", string: "Subject" }],
          },
        ]}
        onDropFieldName={(groupId, name, index) => dropped.push({ groupId, name, index })}
        showChatter={false}
      />,
    );
    const list = screen.getAllByTestId("canvas-drop-list")[0];
    const dataTransfer = {
      getData: (type: string) => (type === ODOO_FIELD_MIME ? "x_priority" : ""),
      types: [ODOO_FIELD_MIME],
      dropEffect: "copy",
      effectAllowed: "copy",
    };
    fireEvent.dragOver(list, { dataTransfer });
    fireEvent.drop(list, { dataTransfer });
    expect(dropped).toEqual([{ groupId: "g1", name: "x_priority", index: 1 }]);
  });

  it("selects a canvas field for the properties rail", () => {
    const selected: string[] = [];
    render(
      <FormCanvas
        title="Ticket"
        groups={[
          {
            id: "g1",
            string: "Identity",
            fields: [{ id: "f1", name: "x_name", string: "Subject" }],
          },
        ]}
        onSelectField={(id) => selected.push(id)}
        showChatter={false}
      />,
    );
    fireEvent.click(screen.getByTestId("canvas-field-x_name").querySelector("button")!);
    expect(selected).toEqual(["f1"]);
  });
});

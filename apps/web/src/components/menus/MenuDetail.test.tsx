/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { MenuNode, WindowActionRow } from "@/lib/api";
import { DEFAULT_ROOT_ICON } from "@/lib/menuForm";
import { MenuDetail } from "./MenuDetail";

vi.mock("next/link", () => ({
  default: ({ children, href, ...rest }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(() => cleanup());

const menus: MenuNode[] = [
  { id: 1, name: "Front desk", parent_id: null, action: null, action_id: null, sequence: 10, web_icon: "base,static/description/icon.png", child_count: 1, group_ids: [] },
  { id: 2, name: "Visitors", parent_id: 1, parent_name: "Front desk", action: "ir.actions.act_window,10", action_id: 10, sequence: 10, web_icon: null, child_count: 0, group_ids: [] },
  { id: 3, name: "Fleet", parent_id: null, action: null, action_id: null, sequence: 20, web_icon: "fleet,static/description/icon.png", child_count: 0, group_ids: [] },
];
const actions: WindowActionRow[] = [{ id: 10, name: "Visitors", res_model: "x_visitor", view_mode: "list,form" }];

function renderDetail(props: Partial<React.ComponentProps<typeof MenuDetail>> = {}) {
  const onSave = vi.fn();
  render(
    <MenuDetail
      connectionId="c1"
      menu={menus[1]}
      menus={menus}
      actions={actions}
      groups={[]}
      onSave={onSave}
      onCreateAndBind={vi.fn()}
      onDelete={vi.fn()}
      {...props}
    />,
  );
  return { onSave };
}

describe("MenuDetail", () => {
  it("makes Save the menu the primary action and disables it until something changes", () => {
    renderDetail();
    const save = screen.getByTestId("menus-detail-save");
    expect(save).toHaveTextContent("Save the menu");
    expect(save).toBeDisabled();
    expect(screen.getByTestId("menus-detail-changes")).toHaveTextContent("No changes");
    expect(screen.getByTestId("menus-detail-path")).toHaveTextContent("Front desk");
  });

  it("summarises changes and saves the patch", () => {
    const { onSave } = renderDetail();
    fireEvent.change(screen.getByLabelText("Sequence"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Parent"), { target: { value: "3" } });
    expect(screen.getByTestId("menus-detail-changes")).toHaveTextContent("2 changes: parent and sequence");
    expect(screen.getByTestId("menus-detail-moved")).toHaveTextContent("Moving from Front desk to Fleet");
    fireEvent.click(screen.getByTestId("menus-detail-save"));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ parent_id: 3, clear_parent: false, sequence: 5 }),
    );
    expect(onSave.mock.calls[0][0]).not.toHaveProperty("web_icon");
  });

  it("follows a parent staged by a drag, and adds the default icon when it becomes top level", () => {
    const onParentChange = vi.fn();
    const { onSave } = renderDetail({ parentValue: "", onParentChange });
    expect(screen.getByTestId("menus-detail-moved")).toHaveTextContent("Moving from Front desk to Top level");
    expect(screen.getByTestId("menus-detail-moved")).toHaveTextContent("default icon path");
    fireEvent.click(screen.getByTestId("menus-detail-save"));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ parent_id: null, clear_parent: true, web_icon: DEFAULT_ROOT_ICON }),
    );
  });

  it("discard puts every field back and tells the tree", () => {
    const onParentChange = vi.fn();
    renderDetail({ onParentChange });
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Guests" } });
    fireEvent.click(screen.getByTestId("menus-detail-discard"));
    expect(screen.getByLabelText("Label")).toHaveValue("Visitors");
    expect(onParentChange).toHaveBeenLastCalledWith("1");
    expect(screen.getByTestId("menus-detail-save")).toBeDisabled();
  });

  it("asks for a label instead of saving an empty one", () => {
    renderDetail();
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: " " } });
    expect(screen.getByText("Enter a label. Odoo shows it in the navbar.")).toBeInTheDocument();
    expect(screen.getByTestId("menus-detail-save")).toBeDisabled();
  });

  it("shows the gate reason and keeps Save off when mutations are blocked", () => {
    renderDetail({ canMutate: false, mutateBlocked: "Read-only connection." });
    fireEvent.change(screen.getByLabelText("Sequence"), { target: { value: "7" } });
    expect(screen.getByTestId("menus-detail-save")).toBeDisabled();
    expect(screen.getByTestId("menus-detail-savebar")).toHaveTextContent("Read-only connection.");
  });
});

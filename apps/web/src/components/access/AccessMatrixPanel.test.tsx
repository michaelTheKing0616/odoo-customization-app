/** @vitest-environment happy-dom */
import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AccessMatrixOut, Connection } from "@/lib/api";
import { accessVersionFrame, accessWriteGate, type MatrixChange } from "@/lib/accessScreen";
import { AccessMatrixPanel } from "./AccessMatrixPanel";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(() => cleanup());

const MATRIX: AccessMatrixOut = {
  models: ["res.partner", "sale.order"],
  groups: [
    { id: 2, name: "User", full_name: "Sales / User", share: false },
    { id: 4, name: "Portal", full_name: "User types / Portal", share: true },
  ],
  cells: [
    {
      model: "res.partner",
      group_id: null,
      access_id: 10,
      name: "pub",
      perm_read: true,
      perm_write: false,
      perm_create: false,
      perm_unlink: false,
      active: true,
    },
    {
      model: "sale.order",
      group_id: 2,
      access_id: 21,
      name: "u",
      perm_read: true,
      perm_write: true,
      perm_create: true,
      perm_unlink: false,
      active: true,
    },
  ],
};

function conn(write_mode: Connection["write_mode"] = "standard", major = 19): Connection {
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

function renderPanel(
  opts: { mode?: Connection["write_mode"]; major?: number; onSave?: () => boolean } = {},
) {
  const major = opts.major ?? 19;
  const onSave = vi.fn<(changes: MatrixChange[]) => boolean>(opts.onSave ?? (() => true));
  render(
    <AccessMatrixPanel
      frame={accessVersionFrame(major)}
      gate={accessWriteGate(conn(opts.mode ?? "standard", major), "c1")}
      modelsInput="res.partner, sale.order"
      onModelsInput={vi.fn()}
      matrix={MATRIX}
      onLoad={vi.fn()}
      onSave={onSave}
    />,
  );
  return { onSave };
}

describe("AccessMatrixPanel", () => {
  it("is a real table with caption, column groups, column and row headers", () => {
    renderPanel();
    const table = screen.getByRole("table");
    expect(table.querySelector("caption")).toHaveTextContent("groups in rows");
    expect(table.querySelectorAll('th[scope="colgroup"]')).toHaveLength(2);
    expect(table.querySelectorAll('thead th[scope="col"]').length).toBe(1 + 2 * 4);
    const rowHeaders = table.querySelectorAll('tbody th[scope="row"]');
    expect(rowHeaders).toHaveLength(3); // global + 2 groups
    expect(rowHeaders[0]).toHaveTextContent("All users");
    expect(rowHeaders[0]).toHaveTextContent("Global");
    expect(screen.getByRole("columnheader", { name: "sale.order" })).toBeInTheDocument();
  });

  it("stages a flip, names it, and saves the right with one teal primary", async () => {
    const { onSave } = renderPanel();
    const save = screen.getByTestId("access-matrix-save");
    expect(save).toBeDisabled();
    expect(save).toHaveTextContent("Save right");

    const pip = screen.getByRole("button", { name: "Delete on sale.order for Sales / User" });
    expect(pip).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(pip);
    expect(pip).toHaveAttribute("aria-pressed", "true");
    expect(pip).toHaveAttribute("data-staged", "true");
    expect(screen.getByTestId("access-savebar-count")).toHaveTextContent("1 change staged");
    expect(screen.getByTestId("access-savebar-detail")).toHaveTextContent(
      "Sales / User gains Delete on sale.order",
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Read on res.partner for User types / Portal" }),
    );
    expect(save).toHaveTextContent("Save 2 rights");
    expect(save).toBeEnabled();

    fireEvent.click(save);
    expect(onSave).toHaveBeenCalledTimes(1);
    const changes = onSave.mock.calls[0][0];
    expect(changes).toHaveLength(2);
    expect(changes.find((c) => c.accessId === 21)?.patch).toEqual({ perm_unlink: true });
    expect(changes.find((c) => c.accessId == null)?.patch).toEqual({ perm_read: true });
    await screen.findByText("No changes staged");

    // One filled teal primary in the whole matrix view.
    expect(document.querySelectorAll("button.bg-accent, a.bg-accent")).toHaveLength(1);
  });

  it("keeps the stage when the save fails", async () => {
    renderPanel({ onSave: () => false });
    fireEvent.click(screen.getByRole("button", { name: "Delete on sale.order for Sales / User" }));
    fireEvent.click(screen.getByTestId("access-matrix-save"));
    await Promise.resolve();
    expect(screen.getByTestId("access-savebar-count")).toHaveTextContent("1 change staged");
  });

  it("discard clears the stage", () => {
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Delete on sale.order for Sales / User" }));
    fireEvent.click(screen.getByTestId("access-matrix-discard"));
    expect(screen.getByTestId("access-savebar-count")).toHaveTextContent("No changes staged");
  });

  it("global row is never toggled in place", () => {
    renderPanel();
    const globalPip = screen.getByRole("button", { name: "Read on res.partner for All users" });
    expect(globalPip).toBeDisabled();
    expect(globalPip).toHaveAttribute("title", expect.stringMatching(/Global lines/));
  });

  it("production: no inline save, cells locked, link to the plan card", () => {
    renderPanel({ mode: "production" });
    expect(screen.queryByTestId("access-matrix-save")).toBeNull();
    const link = screen.getByTestId("access-plan-link");
    expect(link).toHaveAttribute("href", "/approvals?connection_id=c1");
    expect(link).toHaveTextContent("Open plan card");
    expect(
      screen.getByRole("button", { name: "Delete on sale.order for Sales / User" }),
    ).toBeDisabled();
    expect(screen.getByTestId("access-savebar-count")).toHaveTextContent(
      "Inline save is off on production",
    );
  });

  it("Odoo 20 titles the matrix ir.access", () => {
    renderPanel({ major: 20 });
    expect(screen.getByTestId("access-matrix-title")).toHaveTextContent("ir.access matrix");
    expect(screen.getByRole("table").querySelector("caption")).toHaveTextContent(
      "ir.access matrix",
    );
  });

  it("arrow keys move a single roving tab stop through the grid", () => {
    renderPanel();
    const table = screen.getByRole("table");
    const tabbable = table.querySelectorAll('button[tabindex="0"]');
    expect(tabbable).toHaveLength(1);
    const start = tabbable[0] as HTMLButtonElement;
    // Global row is read-only, so entry lands on the first group.
    expect(start.getAttribute("aria-label")).toBe("Read on res.partner for Sales / User");
    start.focus();
    fireEvent.keyDown(start, { key: "ArrowRight" });
    expect(document.activeElement?.getAttribute("aria-label")).toBe(
      "Write on res.partner for Sales / User",
    );
    fireEvent.keyDown(document.activeElement!, { key: "ArrowDown" });
    expect(document.activeElement?.getAttribute("aria-label")).toBe(
      "Write on res.partner for User types / Portal",
    );
    fireEvent.keyDown(document.activeElement!, { key: "ArrowUp" });
    fireEvent.keyDown(document.activeElement!, { key: "ArrowUp" });
    expect(document.activeElement?.getAttribute("aria-label")).toBe(
      "Write on res.partner for Sales / User",
    );
  });

  it("empty matrix explains what, why and next", () => {
    render(
      <AccessMatrixPanel
        frame={accessVersionFrame(19)}
        gate={accessWriteGate(conn(), "c1")}
        modelsInput=""
        onModelsInput={vi.fn()}
        matrix={null}
        onLoad={vi.fn()}
        onSave={vi.fn()}
      />,
    );
    const guide = screen.getByTestId("access-matrix-empty");
    expect(within(guide).getByText("Why")).toBeInTheDocument();
    expect(within(guide).getByText("Next")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

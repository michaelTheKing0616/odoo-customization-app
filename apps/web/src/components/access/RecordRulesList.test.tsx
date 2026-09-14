/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RecordRuleRow } from "@/lib/api";
import { RecordRulesList } from "./RecordRulesList";

afterEach(() => cleanup());

const rows: RecordRuleRow[] = [
  {
    id: 1,
    name: "Own partners",
    model: "res.partner",
    model_id: 8,
    domain_force: "[('create_uid', '=', user.id)]",
    group_ids: [4],
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: true,
    active: true,
  },
  {
    id: 2,
    name: "All tickets",
    model: "x_ticket",
    model_id: 20,
    domain_force: "[]",
    group_ids: [],
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: true,
    active: true,
    global: true,
  },
];

describe("RecordRulesList", () => {
  it("filters by domain and calls onSelect", () => {
    const onSelect = vi.fn();
    render(
      <RecordRulesList
        rows={rows}
        selectedId={null}
        query="create_uid"
        onQueryChange={vi.fn()}
        onSelect={onSelect}
        onCreate={vi.fn()}
      />,
    );
    expect(screen.queryByText("All tickets")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("access-rule-row-1"));
    expect(onSelect).toHaveBeenCalledWith(rows[0]);
  });
});

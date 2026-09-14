/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { GroupRow } from "@/lib/api";
import { GroupPicker } from "./GroupPicker";

afterEach(() => cleanup());

const groups: GroupRow[] = [
  { id: 1, name: "Internal User", full_name: "User types / Internal User", share: false },
  { id: 2, name: "Settings", full_name: "Administration / Settings", share: false },
];

describe("GroupPicker", () => {
  it("toggles a group in multi mode", () => {
    const onChange = vi.fn();
    render(<GroupPicker groups={groups} value={[]} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("User types / Internal User"));
    expect(onChange).toHaveBeenCalledWith([1]);
  });

  it("filters by name", () => {
    render(<GroupPicker groups={groups} value={[]} onChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Filter groups"), { target: { value: "settings" } });
    expect(screen.queryByText("User types / Internal User")).not.toBeInTheDocument();
    expect(screen.getByText("Administration / Settings")).toBeInTheDocument();
  });
});

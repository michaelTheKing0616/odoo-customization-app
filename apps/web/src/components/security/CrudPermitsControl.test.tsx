/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CrudPermitsControl } from "./CrudPermitsControl";

afterEach(() => cleanup());

describe("CrudPermitsControl", () => {
  it("toggles write off", () => {
    const onChange = vi.fn();
    render(
      <CrudPermitsControl
        value={{ perm_read: true, perm_write: true, perm_create: true, perm_unlink: false }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByText("Write"));
    expect(onChange).toHaveBeenCalledWith({ perm_write: false });
  });
});

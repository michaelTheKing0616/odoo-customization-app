/** @vitest-environment jsdom */
import React, { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DomainBuilder } from "./DomainBuilder";

afterEach(() => cleanup());

function ControlledDomain({ initial = "[]" }: { initial?: string }) {
  const [value, setValue] = useState(initial);
  return <DomainBuilder value={value} onChange={setValue} label="Apply on" />;
}

describe("DomainBuilder UI", () => {
  it("shows empty apply-on hint", () => {
    render(<ControlledDomain />);
    expect(screen.getByTestId("domain-builder-empty")).toHaveTextContent(
      "Leave empty to apply on every matching trigger",
    );
  });

  it("shows a valid-domain hint for a parsed apply-on", () => {
    render(<ControlledDomain initial={"[('x_status', '=', 'confirmed')]"} />);
    expect(screen.getByTestId("domain-builder-ok")).toHaveTextContent("Domain looks valid");
  });

  it("reports invalid raw domains", () => {
    render(<ControlledDomain />);
    fireEvent.click(screen.getByRole("button", { name: "Edit raw" }));
    fireEvent.change(screen.getByLabelText("Raw domain"), {
      target: { value: "[('x_status', '=', 'open'" },
    });
    expect(screen.getByTestId("domain-builder-error")).toHaveTextContent("Unbalanced brackets");
  });
});

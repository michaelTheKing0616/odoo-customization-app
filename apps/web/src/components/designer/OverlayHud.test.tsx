/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { OverlayHud } from "@/components/designer/OverlayHud";

describe("OverlayHud", () => {
  afterEach(() => cleanup());

  it("shows an honest empty prompt without a selection", () => {
    render(<OverlayHud fieldName={null} xpath="" />);
    expect(screen.getByTestId("overlay-selected")).toHaveTextContent(/Click a field in the preview/);
    expect(screen.getByTestId("overlay-selected")).toHaveTextContent(/page or group/);
  });

  it("badges a named locator", () => {
    render(
      <OverlayHud fieldName="email" ttype="char" xpath="//field[@name='email']" matchCount={1} />,
    );
    expect(screen.getByTestId("overlay-selected")).toHaveTextContent("email");
    expect(screen.getByTestId("overlay-locator-kind")).toHaveTextContent("Named");
  });

  it("badges positional locators as a warning", () => {
    render(<OverlayHud fieldName="email" xpath="//group[2]/field[1]" />);
    expect(screen.getByTestId("overlay-locator-kind")).toHaveTextContent("Positional");
  });
});

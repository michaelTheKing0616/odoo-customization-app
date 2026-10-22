/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ConfigStateGuide } from "./ConfigStateGuide";

afterEach(() => cleanup());

describe("ConfigStateGuide", () => {
  it("renders what/why/next without em dashes", () => {
    render(
      <ConfigStateGuide
        testId="config-idle-guide"
        guide={{
          title: "Pick a recipe",
          why: "Dry-run first — then apply",
          next: "Open Day-1",
        }}
      />,
    );
    expect(screen.getByTestId("config-idle-guide-title").textContent).toBe("Pick a recipe");
    expect(screen.getByTestId("config-idle-guide-why").textContent).toBe(
      "Dry-run first - then apply",
    );
    expect(screen.getByTestId("config-idle-guide-next").textContent).toBe("Open Day-1");
  });
});

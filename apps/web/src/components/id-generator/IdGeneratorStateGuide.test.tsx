import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { emptyIdGenGuide } from "@/lib/idGeneratorScreen";
import { IdGeneratorStateGuide } from "./IdGeneratorStateGuide";

describe("IdGeneratorStateGuide", () => {
  it("renders why and next", () => {
    render(
      <IdGeneratorStateGuide
        testId="id-generator-empty-guide"
        tone="accent"
        guide={emptyIdGenGuide("csv")}
      />,
    );
    expect(screen.getByTestId("id-generator-empty-guide-why")).toBeTruthy();
    expect(screen.getByTestId("id-generator-empty-guide-next")).toBeTruthy();
    expect(screen.getByTestId("id-generator-empty-guide-title").textContent).toMatch(/preview/i);
  });
});

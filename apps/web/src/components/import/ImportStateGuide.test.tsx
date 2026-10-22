/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ImportStateGuide } from "@/components/import/ImportStateGuide";
import { emptyImportGuide } from "@/lib/importScreen";

afterEach(() => cleanup());

describe("ImportStateGuide", () => {
  it("renders what / why / next empty guide", () => {
    render(
      <div className="import-operate">
        <ImportStateGuide testId="import-empty-guide" guide={emptyImportGuide()} />
      </div>,
    );
    expect(screen.getByTestId("import-empty-guide-title")).toHaveTextContent(/no file parsed/i);
    expect(screen.getByTestId("import-empty-guide-why").textContent?.length).toBeGreaterThan(10);
    expect(screen.getByTestId("import-empty-guide-next").textContent?.toLowerCase()).toContain("parse");
    expect(screen.getByTestId("import-empty-guide").textContent).not.toMatch(/\u2014|\u2013/);
  });

  it("renders brief density without card guide chrome", () => {
    render(
      <div className="import-operate op-studio-shell">
        <ImportStateGuide density="brief" testId="import-brief-guide" guide={emptyImportGuide()} />
      </div>,
    );
    const root = screen.getByTestId("import-brief-guide");
    expect(root.className).toContain("op-brief");
    expect(root.getAttribute("data-tone")).toBeNull();
  });
});

/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImportResultCounts } from "@/components/import/ImportResultCounts";

describe("ImportResultCounts", () => {
  it("shows create update skip error counts", () => {
    render(
      <div className="import-operate">
        <ImportResultCounts
          strip={{
            created: 4,
            updated: 1,
            skipped: 2,
            failed: 3,
            dryRun: true,
            ok: false,
            message: "preview",
            hasErrorCsv: true,
          }}
        />
      </div>,
    );
    expect(screen.getByTestId("import-result-counts")).toHaveAttribute("data-dry-run", "true");
    expect(screen.getByTestId("import-result-counts-created")).toHaveTextContent("4");
    expect(screen.getByTestId("import-result-counts-failed")).toHaveTextContent("3");
  });
});

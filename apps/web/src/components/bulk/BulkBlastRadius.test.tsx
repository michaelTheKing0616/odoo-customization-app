/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BulkBlastRadius } from "./BulkBlastRadius";
import { blastRadiusFromState } from "@/lib/bulkSuiteScreen";

describe("BulkBlastRadius", () => {
  it("shows known count before run", () => {
    const blast = blastRadiusFromState({
      model: "res.partner",
      selectionMode: "ids",
      idsText: "1,2,3,4",
    });
    render(<BulkBlastRadius blast={blast} />);
    expect(screen.getByTestId("bulk-blast-radius")).toHaveAttribute("data-known", "true");
    expect(screen.getByTestId("bulk-blast-radius-label")).toHaveTextContent(/4 records/);
  });
});

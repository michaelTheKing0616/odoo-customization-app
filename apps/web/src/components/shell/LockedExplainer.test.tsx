import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LockedExplainer } from "./LockedExplainer";

describe("LockedExplainer", () => {
  it("shows why and Expert handoff", () => {
    render(
      <LockedExplainer
        title="Grid view locked"
        why="Needs Enterprise web_grid on this instance."
        options={["Export module", "Use staging EE"]}
        connectionId="c1"
      />,
    );
    expect(screen.getByTestId("locked-explainer")).toBeInTheDocument();
    expect(screen.getByTestId("locked-explainer-why")).toHaveTextContent(/Enterprise/);
    expect(screen.getByRole("link", { name: /Ask Expert why/i })).toHaveAttribute(
      "href",
      "/connections/c1/expert",
    );
  });
});

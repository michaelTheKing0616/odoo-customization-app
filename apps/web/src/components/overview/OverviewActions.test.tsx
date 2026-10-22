import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { OverviewActions } from "./OverviewHomeChrome";

afterEach(cleanup);

describe("OverviewActions", () => {
  it("has App Studio as the only primary action and the rest in a More menu", async () => {
    render(<OverviewActions connectionId="c1" />);
    expect(screen.getByTestId("overview-draft-with-ai")).toHaveAttribute("href", "/connections/c1/studio");
    expect(screen.queryByText("Client command")).toBeNull();
    const more = screen.getByRole("button", { name: /More/ });
    fireEvent.click(more);
    const items = await screen.findAllByRole("menuitem");
    expect(items.map((i) => i.textContent)).toEqual(["Client command", "Open Builder", "Projects"]);
    expect(screen.getByTestId("overview-projects")).toHaveAttribute("href", "/connections/c1/projects");
  });
});

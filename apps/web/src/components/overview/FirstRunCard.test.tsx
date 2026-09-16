import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import { FirstRunCard } from "@/components/overview/FirstRunCard";

describe("FirstRunCard (UIF-3)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("shows when there are zero models and dismisses", () => {
    render(<FirstRunCard connectionId="conn-1" modelCount={0} />);
    expect(screen.getByTestId("overview-first-run")).toBeInTheDocument();
    expect(screen.getByTestId("overview-first-run-app-studio")).toHaveAttribute(
      "href",
      "/connections/conn-1/studio",
    );
    expect(screen.getByTestId("overview-first-run-projects")).toHaveAttribute(
      "href",
      "/connections/conn-1/projects",
    );
    fireEvent.click(screen.getByTestId("overview-first-run-dismiss"));
    expect(screen.queryByTestId("overview-first-run")).not.toBeInTheDocument();
  });

  it("hides when models exist", () => {
    render(<FirstRunCard connectionId="conn-1" modelCount={3} />);
    expect(screen.queryByTestId("overview-first-run")).not.toBeInTheDocument();
  });
});

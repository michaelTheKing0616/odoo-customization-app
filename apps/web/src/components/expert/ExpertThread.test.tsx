/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ExpertThread } from "./ExpertThread";

afterEach(() => cleanup());

describe("ExpertThread", () => {
  it("shows empty honesty, loading, error, and collapsed error logs", () => {
    const { rerender } = render(
      <ExpertThread turns={[]} onSelectPrompt={() => undefined} connectionId="c1" />,
    );
    expect(screen.getByTestId("expert-empty")).toBeTruthy();

    rerender(
      <ExpertThread
        turns={[{ role: "user", content: "Diagnose this\n\nError log:\nAccessError: denied" }]}
        busy
        error="Expert unavailable: timeout"
        onSelectPrompt={() => undefined}
        connectionId="c1"
      />,
    );
    expect(screen.getByText("Diagnose this")).toBeTruthy();
    expect(screen.getByText("Error log")).toBeTruthy();
    expect(screen.getByTestId("expert-loading").textContent).toMatch(/Retrieving sources/);
    expect(screen.getByTestId("expert-error").textContent).toMatch(/timeout/);
  });
});

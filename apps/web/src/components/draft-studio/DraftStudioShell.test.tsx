/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DraftStudioShell } from "./DraftStudioShell";

afterEach(() => cleanup());

describe("DraftStudioShell", () => {
  it("keeps Draft Studio identity and the stable page testid", () => {
    render(
      <DraftStudioShell
        connectionId="c1"
        connectionName="Lab 19"
        journey={{ id: "prompt" }}
      >
        <p>prompt body</p>
      </DraftStudioShell>,
    );
    expect(screen.getByTestId("draft-studio")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Draft Studio" })).toBeTruthy();
    expect(screen.getByText(/Lab 19/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "App Studio" })).toHaveAttribute(
      "href",
      "/connections/c1/studio",
    );
    expect(screen.getByTestId("draft-studio-steps")).toBeTruthy();
  });
});

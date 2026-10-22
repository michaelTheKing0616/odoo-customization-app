/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { emptySettingsGuide } from "@/lib/settingsScreen";
import { SettingsStateGuide } from "./SettingsStateGuide";

afterEach(() => cleanup());

describe("SettingsStateGuide", () => {
  it("renders why and next", () => {
    render(
      <SettingsStateGuide
        testId="settings-empty-guide"
        tone="accent"
        guide={emptySettingsGuide()}
      />,
    );
    expect(screen.getByTestId("settings-empty-guide-why")).toBeTruthy();
    expect(screen.getByTestId("settings-empty-guide-next")).toBeTruthy();
    expect(screen.getByTestId("settings-empty-guide-title").textContent).toMatch(/No API keys/i);
  });
});

/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: vi.fn(),
}));

import { ConfigErrorNotice } from "./ConfigErrorNotice";

afterEach(() => cleanup());

describe("ConfigErrorNotice", () => {
  it("classifies timeout into what/why/next", () => {
    render(
      <ConfigErrorNotice message="Connection timed out while loading" context="load" />,
    );
    expect(screen.getByTestId("config-error-notice")).toBeTruthy();
    expect(screen.getByTestId("config-error-why").textContent?.toLowerCase()).toMatch(
      /took too long|timed/,
    );
    expect(screen.getByTestId("config-error-next").textContent?.length).toBeGreaterThan(5);
  });
});

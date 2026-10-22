import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  HousekeepingStepRail,
  resolveHousekeepingStep,
} from "./HousekeepingStepRail";
import { formatBytes } from "./formatBytes";

describe("resolveHousekeepingStep", () => {
  it("starts at scan with no work", () => {
    expect(
      resolveHousekeepingStep({
        hasScan: false,
        hasSelection: false,
        hasDryRunResult: false,
        hasCleanResult: false,
      }),
    ).toBe("scan");
  });

  it("moves to review once a scan or selection exists", () => {
    expect(
      resolveHousekeepingStep({
        hasScan: true,
        hasSelection: false,
        hasDryRunResult: false,
        hasCleanResult: false,
      }),
    ).toBe("review");
    expect(
      resolveHousekeepingStep({
        hasScan: false,
        hasSelection: true,
        hasDryRunResult: false,
        hasCleanResult: false,
      }),
    ).toBe("review");
  });

  it("prefers dry-run then clean", () => {
    expect(
      resolveHousekeepingStep({
        hasScan: true,
        hasSelection: true,
        hasDryRunResult: true,
        hasCleanResult: false,
      }),
    ).toBe("dry-run");
    expect(
      resolveHousekeepingStep({
        hasScan: true,
        hasSelection: true,
        hasDryRunResult: true,
        hasCleanResult: true,
      }),
    ).toBe("clean");
  });
});

describe("HousekeepingStepRail", () => {
  it("marks the current step", () => {
    render(<HousekeepingStepRail current="dry-run" />);
    expect(screen.getByTestId("housekeeping-step-rail-dry-run")).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(screen.getByTestId("housekeeping-step-rail-scan")).not.toHaveAttribute(
      "data-active",
    );
  });
});

describe("formatBytes", () => {
  it("formats common sizes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(1_048_576)).toBe("1.0 MB");
  });
});

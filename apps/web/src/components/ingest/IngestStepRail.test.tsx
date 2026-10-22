import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IngestStepRail, resolveIngestStep } from "./IngestStepRail";

describe("resolveIngestStep", () => {
  it("starts at upload with no job", () => {
    expect(
      resolveIngestStep({ hasJob: false, hasDryRunLog: false, hasCommitLog: false }),
    ).toBe("upload");
  });

  it("stays on classify when types need confirm", () => {
    expect(
      resolveIngestStep({
        hasJob: true,
        needsTypeConfirm: true,
        hasDryRunLog: false,
        hasCommitLog: false,
      }),
    ).toBe("classify");
  });

  it("moves to plan when a job exists", () => {
    expect(
      resolveIngestStep({ hasJob: true, hasDryRunLog: false, hasCommitLog: false }),
    ).toBe("plan");
  });

  it("prefers dry-run then commit", () => {
    expect(
      resolveIngestStep({ hasJob: true, hasDryRunLog: true, hasCommitLog: false }),
    ).toBe("dry-run");
    expect(
      resolveIngestStep({ hasJob: true, hasDryRunLog: true, hasCommitLog: true }),
    ).toBe("commit");
  });
});

describe("IngestStepRail", () => {
  it("marks the current step", () => {
    render(<IngestStepRail current="dry-run" />);
    expect(screen.getByTestId("ingest-step-rail-dry-run")).toHaveAttribute(
      "data-state",
      "current",
    );
    expect(screen.getByTestId("ingest-step-rail-upload")).toHaveAttribute(
      "data-state",
      "done",
    );
  });
});

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  SandboxDeployStages,
  sandboxDeployCurrentIndex,
} from "./SandboxDeployStages";

describe("SandboxDeployStages", () => {
  it("renders four phases", () => {
    render(<SandboxDeployStages currentIndex={1} />);
    expect(screen.getByTestId("sandbox-deploy-stages")).toBeInTheDocument();
    expect(screen.getByText("Package")).toBeInTheDocument();
    expect(screen.getByText("Promote")).toBeInTheDocument();
  });
});

describe("sandboxDeployCurrentIndex", () => {
  it("maps validation and promote", () => {
    expect(sandboxDeployCurrentIndex({ hasValidationId: false, promotedCount: 0 })).toBe(0);
    expect(sandboxDeployCurrentIndex({ hasValidationId: true, promotedCount: 0 })).toBe(2);
    expect(sandboxDeployCurrentIndex({ hasValidationId: true, promotedCount: 1 })).toBe(3);
  });
});

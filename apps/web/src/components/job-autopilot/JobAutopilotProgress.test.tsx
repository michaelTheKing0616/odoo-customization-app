/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { JobAutopilotProgress } from "./JobAutopilotProgress";

afterEach(() => cleanup());

describe("JobAutopilotProgress", () => {
  it("tells the operator leave-and-return resumes or opens the last result", () => {
    render(<JobAutopilotProgress label="Running Autopilot" />);
    const honesty = screen.getByTestId("job-autopilot-progress-honesty").textContent ?? "";
    expect(honesty).toMatch(/Returning here resumes this job/);
    expect(honesty).toMatch(/opens the last result/);
    expect(honesty).not.toMatch(/the job keeps running/);
    expect(honesty).not.toMatch(/!/);
  });
});

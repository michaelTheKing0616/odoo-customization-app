import { afterEach, describe, expect, it } from "vitest";
import {
  classifyJobAutopilotResume,
  forgetJobAutopilot,
  jobProgressHonestyLine,
  jobResumeNotice,
  readRememberedJobAutopilot,
  rememberJobAutopilot,
} from "./job-autopilot-resume";

afterEach(() => {
  try {
    sessionStorage.clear();
  } catch {
    /* jsdom */
  }
});

describe("job Autopilot resume storage", () => {
  it("round-trips a job id for the same connection", () => {
    expect(readRememberedJobAutopilot("c1")).toBeNull();
    rememberJobAutopilot("c1", "job-99");
    expect(readRememberedJobAutopilot("c1")).toBe("job-99");
    expect(readRememberedJobAutopilot("c2")).toBeNull();
    forgetJobAutopilot("c1");
    expect(readRememberedJobAutopilot("c1")).toBeNull();
  });
});

describe("classifyJobAutopilotResume", () => {
  it("resumes running jobs and hydrates finished ones without inventing another connection's job", () => {
    expect(
      classifyJobAutopilotResume({ status: "running", connection_id: "c1" }, "c1"),
    ).toBe("running");
    expect(
      classifyJobAutopilotResume({ status: "queued", connection_id: "c1" }, "c1"),
    ).toBe("running");
    expect(
      classifyJobAutopilotResume({ status: "succeeded", connection_id: "c1" }, "c1"),
    ).toBe("succeeded");
    expect(
      classifyJobAutopilotResume({ status: "failed", connection_id: "c1" }, "c1"),
    ).toBe("failed");
    expect(
      classifyJobAutopilotResume({ status: "running", connection_id: "other" }, "c1"),
    ).toBe("stale");
  });
});

describe("honesty copy", () => {
  it("promises leave-and-return only because resume is wired", () => {
    const line = jobProgressHonestyLine();
    expect(line).toMatch(/Returning here resumes this job/);
    expect(line).toMatch(/opens the last result/);
    expect(line).not.toMatch(/the job keeps running$/);
    expect(line).not.toMatch(/!/);
    expect(jobResumeNotice("stale")).toMatch(/Start a new run/);
    expect(jobResumeNotice("failed")).not.toMatch(/keeps running/);
  });
});

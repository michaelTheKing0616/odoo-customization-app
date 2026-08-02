import { describe, expect, it, vi } from "vitest";
import type { JobRow } from "./api";
import { JobPollError, pollJob } from "./jobs";

function job(partial: Partial<JobRow> & Pick<JobRow, "status">): JobRow {
  return {
    id: "job-1",
    kind: "sandbox",
    connection_id: "conn-1",
    result: null,
    error: null,
    created_at: null,
    finished_at: null,
    ...partial,
  };
}

describe("pollJob", () => {
  it("returns when status becomes succeeded", async () => {
    const fetchJob = vi
      .fn()
      .mockResolvedValueOnce(job({ status: "running" }))
      .mockResolvedValueOnce(
        job({
          status: "succeeded",
          result: { validation_id: "val-1", zip_base64: "Zm9v" },
        }),
      );
    const sleep = vi.fn(async () => undefined);
    const onUpdate = vi.fn();

    const result = await pollJob("job-1", {
      fetchJob,
      sleep,
      intervalMs: 10,
      onUpdate,
    });

    expect(result.status).toBe("succeeded");
    expect(result.result?.validation_id).toBe("val-1");
    expect(fetchJob).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledWith(10);
    expect(onUpdate).toHaveBeenCalledTimes(2);
  });

  it("throws JobPollError when status is failed", async () => {
    const fetchJob = vi.fn().mockResolvedValue(
      job({ status: "failed", error: "sandbox exploded" }),
    );

    await expect(
      pollJob("job-1", { fetchJob, sleep: async () => undefined }),
    ).rejects.toBeInstanceOf(JobPollError);

    try {
      await pollJob("job-1", { fetchJob, sleep: async () => undefined });
    } catch (err) {
      expect(err).toBeInstanceOf(JobPollError);
      expect((err as JobPollError).message).toBe("sandbox exploded");
      expect((err as JobPollError).job?.status).toBe("failed");
    }
  });

  it("throws on timeout after maxAttempts", async () => {
    const fetchJob = vi.fn().mockResolvedValue(job({ status: "queued" }));
    const sleep = vi.fn(async () => undefined);

    await expect(
      pollJob("job-1", {
        fetchJob,
        sleep,
        maxAttempts: 3,
        intervalMs: 5,
      }),
    ).rejects.toThrow(/timed out/);

    expect(fetchJob).toHaveBeenCalledTimes(3);
    expect(sleep).toHaveBeenCalledTimes(2);
  });
});

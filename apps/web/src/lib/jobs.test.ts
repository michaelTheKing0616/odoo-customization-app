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

  it("throws JobPollError when status is timeout", async () => {
    const fetchJob = vi.fn().mockResolvedValue(
      job({ status: "timeout", error: "Job exceeded 1800s limit" }),
    );

    await expect(
      pollJob("job-1", { fetchJob, sleep: async () => undefined }),
    ).rejects.toMatchObject({ message: "Job exceeded 1800s limit" });
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

  it("retries transient ECONNRESET then succeeds", async () => {
    const fetchJob = vi
      .fn()
      .mockRejectedValueOnce(
        new Error("Cannot reach API at http://127.0.0.1:8001: read ECONNRESET"),
      )
      .mockResolvedValueOnce(job({ status: "succeeded" }));
    const sleep = vi.fn(async () => undefined);

    const result = await pollJob("job-1", {
      fetchJob,
      sleep,
      intervalMs: 10,
      maxAttempts: 5,
    });

    expect(result.status).toBe("succeeded");
    expect(fetchJob).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledTimes(1);
  });

  it("keeps polling when step_label advances past the stale window", async () => {
    const fetchJob = vi
      .fn()
      .mockResolvedValueOnce(job({ status: "running", result: { step_label: "stock" } }))
      .mockResolvedValueOnce(job({ status: "running", result: { step_label: "stock" } }))
      .mockResolvedValueOnce(job({ status: "running", result: { step_label: "smoke" } }))
      .mockResolvedValueOnce(job({ status: "succeeded", result: { step_label: "smoke" } }));
    const sleep = vi.fn(async () => undefined);

    const result = await pollJob("job-1", {
      fetchJob,
      sleep,
      staleAttempts: 2,
      maxAttempts: 10,
    });

    expect(result.status).toBe("succeeded");
    expect(fetchJob).toHaveBeenCalledTimes(4);
  });

  it("throws when a running job stops advancing", async () => {
    const fetchJob = vi.fn().mockResolvedValue(
      job({ status: "running", result: { step_label: "smoke" } }),
    );

    await expect(
      pollJob("job-1", {
        fetchJob,
        sleep: async () => undefined,
        staleAttempts: 2,
        maxAttempts: 20,
      }),
    ).rejects.toThrow(/stalled/);
  });

  it("untilTerminal does not abort a long running stage", async () => {
    const fetchJob = vi
      .fn()
      .mockResolvedValueOnce(job({ status: "running", result: { step_label: "custom" } }))
      .mockResolvedValueOnce(job({ status: "running", result: { step_label: "custom" } }))
      .mockResolvedValueOnce(job({ status: "running", result: { step_label: "custom" } }))
      .mockResolvedValueOnce(job({ status: "succeeded", result: { step_label: "custom" } }));

    const result = await pollJob("job-1", {
      fetchJob,
      sleep: async () => undefined,
      untilTerminal: true,
      staleAttempts: 2,
      maxAttempts: 20,
    });

    expect(result.status).toBe("succeeded");
    expect(fetchJob).toHaveBeenCalledTimes(4);
  });
});

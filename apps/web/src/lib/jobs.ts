import type { JobRow } from "./api";

export type PollJobOptions = {
  /** Interval between polls in ms. Default 2000. */
  intervalMs?: number;
  /** Max polls before giving up. Default 180 (~6 min at 2s). */
  maxAttempts?: number;
  /** Called after each poll with the latest job row. */
  onUpdate?: (job: JobRow) => void;
  /** Inject sleep for tests. Default: real setTimeout. */
  sleep?: (ms: number) => Promise<void>;
  /** Inject fetch for tests. Default: caller must pass via fetchJob. */
  fetchJob: (jobId: string) => Promise<JobRow>;
};

export class JobPollError extends Error {
  readonly job: JobRow | null;

  constructor(message: string, job: JobRow | null = null) {
    super(message);
    this.name = "JobPollError";
    this.job = job;
  }
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Poll GET /api/jobs/{id} until status is succeeded or failed.
 * Throws JobPollError on failure or timeout.
 */
export async function pollJob(
  jobId: string,
  options: PollJobOptions,
): Promise<JobRow> {
  const intervalMs = options.intervalMs ?? 2000;
  const maxAttempts = options.maxAttempts ?? 180;
  const sleep = options.sleep ?? defaultSleep;
  const { fetchJob, onUpdate } = options;

  let last: JobRow | null = null;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    last = await fetchJob(jobId);
    onUpdate?.(last);
    if (last.status === "succeeded") {
      return last;
    }
    if (last.status === "failed" || last.status === "cancelled") {
      throw new JobPollError(
        last.error || `Job ${jobId} ${last.status}`,
        last,
      );
    }
    if (attempt < maxAttempts - 1) {
      await sleep(intervalMs);
    }
  }
  throw new JobPollError(
    `Job ${jobId} timed out after ${maxAttempts} polls (last status: ${last?.status ?? "unknown"})`,
    last,
  );
}

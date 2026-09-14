import type { JobRow } from "./api";

export type PollJobOptions = {
  /** Interval between polls in ms. Default 2000. */
  intervalMs?: number;
  /** Hard cap on polls. Default 180. Ignored as a fail-fast while running if untilTerminal. */
  maxAttempts?: number;
  /**
   * When true, keep polling while status is queued/running. Only stop on a
   * backend terminal status (or maxAttempts as a last-resort safety net).
   * Do not use staleAttempts — a long Expert/install step is not a hang.
   */
  untilTerminal?: boolean;
  /**
   * Give up after this many polls with the same status + step_label.
   * Ignored when untilTerminal is true. Default: maxAttempts.
   */
  staleAttempts?: number;
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

function isTransientPollError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  return /econnreset|econnrefused|fetch failed|cannot reach api|timed out reaching|socket hang up|empty response/i.test(
    err.message,
  );
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
  const untilTerminal = options.untilTerminal === true;
  const staleLimit = untilTerminal ? Number.POSITIVE_INFINITY : (options.staleAttempts ?? maxAttempts);
  const sleep = options.sleep ?? defaultSleep;
  const { fetchJob, onUpdate } = options;

  let last: JobRow | null = null;
  let transient = 0;
  let stale = 0;
  let fingerprint = "";
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      last = await fetchJob(jobId);
      transient = 0;
    } catch (err) {
      if (isTransientPollError(err) && transient < 8) {
        transient += 1;
        if (attempt < maxAttempts - 1) {
          await sleep(intervalMs);
        }
        continue;
      }
      throw err;
    }
    onUpdate?.(last);
    if (last.status === "succeeded") {
      return last;
    }
    if (
      last.status === "failed" ||
      last.status === "cancelled" ||
      last.status === "timeout" ||
      last.status === "interrupted"
    ) {
      throw new JobPollError(
        last.error || `Job ${jobId} ${last.status}`,
        last,
      );
    }
    const fp = `${last.status}:${String(last.result?.step_label ?? "")}:${Array.isArray(last.result?.stages) ? last.result.stages.length : 0}`;
    if (fp === fingerprint) {
      stale += 1;
    } else {
      fingerprint = fp;
      stale = 0;
    }
    if (!untilTerminal && stale >= staleLimit) {
      throw new JobPollError(
        `Job ${jobId} stalled after ${staleLimit} polls with no progress (last status: ${last.status})`,
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

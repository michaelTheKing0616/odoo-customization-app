/** Client progress run id for stage polling. */

export function newProgressRunId(prefix: string): string {
  const tail =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${tail}`;
}

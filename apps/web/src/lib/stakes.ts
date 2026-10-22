/** Touch 97: wording set by stakes. Light on a test copy, firmer and fuller near deletes, money and Live. */
export type Stakes = "low" | "medium" | "high";

export function stakesFor(opts: { danger: boolean; environment?: "Live" | "Test copy" | null; certain?: boolean }): Stakes {
  const live = opts.environment === "Live";
  if (opts.danger && live) return "high";
  if (opts.danger || live || (opts.environment && !opts.certain)) return "medium";
  return "low";
}

export function stakesLine(stakes: Stakes): string {
  switch (stakes) {
    case "high":
      return "This changes your live Odoo, and people using it will see the result straight away. Read every line below before you type the phrase.";
    case "medium":
      return "Take a moment to check the details below before you confirm.";
    default:
      return "This is a test copy, so it's safe to try.";
  }
}

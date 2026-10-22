/**
 * UI-S-18 Code Studio studio-bar helpers. Pure, no React.
 */

export const PAGE_TITLE = "Code Studio";
export const PAGE_DESCRIPTION =
  "Write a server-action body, validate it, then choose a path. Live bind and custom code stay separate.";

export type CodeStudioGuide = { title: string; why: string; next: string };

export function sanitizeCodeStudioCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function codeStudioHonestyGuide(): CodeStudioGuide {
  return {
    title: "Validate before anything runs. Custom code never installs from here.",
    why: "Live bind writes state=code only after Validate, the probe, the confirm phrase, and a snapshot. Custom code downloads a zip; a person publishes it.",
    next: "Compose the body, Validate, then Live bind or Download custom-code zip.",
  };
}

export function codeStudioSessionBadge(status: string | undefined): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  const s = (status || "ready").toLowerCase();
  if (s.includes("block") || s.includes("error")) return { label: "Blocked", variant: "danger" };
  if (s.includes("valid")) return { label: "Validated", variant: "success" };
  if (s.includes("stale")) return { label: "Stale", variant: "warning" };
  return { label: "Ready", variant: "default" };
}

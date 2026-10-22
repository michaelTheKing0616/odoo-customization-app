/**
 * Mirror of apps/api app/ai_conversation/grounding.py brief_wants_llm:
 * long or structured briefs get the AI step on unless the user unchecked it.
 */
export const LONG_BRIEF_WORDS = 60;

export function briefWantsAi(prompt: string | null | undefined): boolean {
  const text = (prompt ?? "").trim();
  if (!text) return false;
  if (text.split(/\s+/).length >= LONG_BRIEF_WORDS) return true;
  if (/^\s{0,3}#{1,6}\s+\S/m.test(text)) return true;
  const numbered = text.split("\n").filter((line) => /^\s*\d+[.)]\s+\S/.test(line)).length;
  return numbered >= 3;
}

/** Explicit user choice (true/false) wins; null means "not chosen yet", so follow the brief. */
export function effectiveAiStep(explicit: boolean | null | undefined, prompt: string | null | undefined): boolean {
  return typeof explicit === "boolean" ? explicit : briefWantsAi(prompt);
}

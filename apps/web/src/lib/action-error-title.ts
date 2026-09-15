/** Titles come from the action that failed — never from scanning the error body. */

export function actionErrorTitle(
  stepOrMessage: string | null | undefined,
  titles: Record<string, string>,
  fallback: string,
  message?: string | null,
): string {
  if (stepOrMessage && titles[stepOrMessage]) {
    return titles[stepOrMessage];
  }
  const text = (stepOrMessage || message || "").trim();
  if (!text) return fallback;
  for (const title of Object.values(titles)) {
    if (text === title) return title;
  }
  return fallback;
}

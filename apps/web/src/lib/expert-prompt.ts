/** True for vertical/module-stack setup questions — each gets a fresh retrieval context. */
export function isExpertSetupStackQuestion(question: string): boolean {
  return /\b(what do i need|what do we need|which modules|which apps|modules do i need|apps do i need|module stack|setup|set up|build an odoo|odoo db for|database for)\b/i.test(
    question,
  );
}

/** Build a visible Expert question that includes pasted RPC / validation errors. */
export function formatExpertDiagnosePrompt(question: string, errorText?: string): string {
  const q = (question || "Diagnose this error on my connection").trim();
  const err = errorText?.trim();
  if (!err) return q;
  if (q.includes(err)) return q;
  return `${q}\n\nError log:\n${err}`;
}

export function buildExpertAskPayload(mainInput: string, errorPaste: string): {
  question: string;
  pastedError?: string;
} {
  const q = mainInput.trim();
  const err = errorPaste.trim();
  if (!err || q.includes(err)) {
    return { question: q, pastedError: err || undefined };
  }
  if (/\nError log:\n/i.test(q)) {
    return { question: q, pastedError: err };
  }
  return {
    question: `${q}\n\nError log:\n${err}`,
    pastedError: err,
  };
}

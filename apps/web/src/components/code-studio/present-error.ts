/** Customer-facing Code Studio error copy. Technical dumps stay in details. */

export type PresentedCodeStudioError = {
  message: string;
  details?: string;
};

function looksLikeTechnicalDump(raw: string): boolean {
  return (
    /traceback \(most recent call last\)/i.test(raw) ||
    /\bpsycopg\b/i.test(raw) ||
    /file ".+", line \d+/i.test(raw) ||
    /authentication rpc failed/i.test(raw) ||
    (raw.includes("\n") && /rpc failed|operationalerror|xmlrpc|jsonrpc/i.test(raw)) ||
    raw.length > 280
  );
}

function customerSentenceFor(raw: string): string {
  if (/database .+ does not exist|psycopg|operationalerror/i.test(raw)) {
    return "The connection database is not reachable.";
  }
  if (/authentication rpc failed|invalid (api.?key|password|credentials)|access denied/i.test(raw)) {
    return "This connection could not sign in to Odoo.";
  }
  if (/timed? ?out|econnrefused|connection refused|cannot reach/i.test(raw)) {
    return "This connection could not reach the Odoo instance.";
  }
  return "This connection could not be reached.";
}

export function presentCodeStudioError(raw: string): PresentedCodeStudioError {
  if (!looksLikeTechnicalDump(raw)) {
    return { message: raw };
  }
  const message = customerSentenceFor(raw);
  return raw === message ? { message } : { message, details: raw };
}

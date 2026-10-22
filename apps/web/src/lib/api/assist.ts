// HOWDO-01: how-do-I assistant contract mirror (types and calls only; no UI).
// Field names follow AI_IN_ODOO.md §HOWDO §6; a backend test compares them.
import { getApiBase } from "./client";

export type AssistTokenRequest = {
  connection_id: string;
  odoo_uid?: number | null;
};

export type HowdoToken = {
  token: string;
  expires_at: string;
  scope: "ask";
};

export type AssistAsk = {
  question: string;
  page_context?: Record<string, string> | null;
};

export type AssistStep = {
  text: string;
  menu_path?: string | null;
  deep_link?: string | null;
};

export type AssistCitation = {
  kind: "doc" | "field" | "menu";
  tech_name: string;
};

export type AssistAnswer = {
  answer_md: string;
  steps: AssistStep[];
  citations: AssistCitation[];
  refused: string | null;
};

async function post<T>(path: string, body: unknown, bearer: string): Promise<T> {
  const res = await fetch(`${getApiBase()}/api/bridge-assist${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${bearer}` },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.error?.message ?? data?.detail?.message ?? `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data as T;
}

/** Called by the bridge addon controller with the integration key. */
export function mintAssistToken(body: AssistTokenRequest, integrationKey: string): Promise<HowdoToken> {
  return post<HowdoToken>("/token", body, integrationKey);
}

/** Ask with the short assistant token (never the integration key). */
export function askAssist(body: AssistAsk, token: string): Promise<AssistAnswer> {
  return post<AssistAnswer>("/ask", body, token);
}

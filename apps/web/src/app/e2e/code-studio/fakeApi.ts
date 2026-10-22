/**
 * Fake connection for the Code Studio harness, so the screen renders without a live API
 * (and never shows a raw request error). The real request goes first: Playwright route mocks
 * (including their deliberate error states) still win. Only a network failure or a 404 on one of
 * the few reads Code Studio makes on load falls back to this fixture.
 */
const CONN = {
  id: "demo-conn",
  name: "Lagos Sessions",
  url: "http://127.0.0.1:8069",
  db_name: "odoo",
  username: "admin",
  server_version: "19.0",
  write_mode: "standard",
  hosting: "self_hosted",
  created_at: null,
  updated_at: null,
  capabilities: {
    major: 19,
    edition: "community",
    server_version: "19.0",
    supported: ["code_server_actions"],
    unsupported: [],
    ga: true,
    message: "ok",
    hosting_hint: "self_hosted",
    installed_modules_sample: ["base", "web"],
  },
};

const GATE = {
  probe: { supported: true },
  gating: {
    feature: "code_studio",
    title: "Live code server actions",
    why: "This database accepts code server actions.",
    options: [],
    available: true,
    capability_key: "code_server_actions",
    gating_choices: [],
  },
  developer_role_required: true,
  entitlement_key: "dev_tools",
};

const MODELS = [
  { id: 1, model: "res.partner", name: "Contact", state: "base", transient: false },
  { id: 2, model: "sale.order", name: "Sales Order", state: "base", transient: false },
  { id: 3, model: "x_session_booking", name: "Session booking", state: "manual", transient: false },
];

const CONTEXT = {
  major: 19,
  symbols: [
    { name: "env", description: "Odoo environment for the current user." },
    { name: "record", description: "The record the action runs on, or None." },
    { name: "records", description: "Records the action runs on." },
    { name: "log", description: "Write a line to the Odoo log." },
    { name: "UserError", description: "Raise to stop with a message for the user." },
  ],
};

const SNIPPETS = {
  snippets: [
    { id: "set_field", label: "Set a field on each record", code: "for rec in records:\n    rec.write({'x_flag': True})" },
    { id: "guard", label: "Stop with a message", code: "if not record.email:\n    raise UserError('Add an email first.')" },
  ],
};

export function fakeResponse(url: string, method: string): unknown | undefined {
  if (method !== "GET") return undefined;
  const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
  if (/\/api\/connections\/demo-conn$/.test(path)) return CONN;
  if (/\/api\/connections\/demo-conn\/code-studio\/gate$/.test(path)) return GATE;
  if (/\/api\/connections\/demo-conn\/code-studio\/context$/.test(path)) return CONTEXT;
  if (/\/api\/connections\/demo-conn\/code-studio\/snippets$/.test(path)) return SNIPPETS;
  if (/\/api\/connections\/demo-conn\/code-studio\/probe$/.test(path)) return { supported: true };
  if (/\/api\/connections\/demo-conn\/models$/.test(path)) return MODELS;
  return undefined;
}

let installed = false;
export function installFakeApi(): void {
  if (installed || typeof window === "undefined") return;
  installed = true;
  const real = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    const body = fakeResponse(url, method);
    if (body === undefined) return real(input, init);
    try {
      const res = await real(input, init);
      if (res.status !== 404) return res;
    } catch {
      // no API running: use the fixture below
    }
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  };
}

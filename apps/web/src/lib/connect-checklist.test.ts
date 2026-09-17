import { describe, expect, it } from "vitest";
import {
  buildConnectChecklist,
  credentialFieldCopy,
  formatAuthFailureHint,
  hostCapabilityBullets,
  apiKeyGuideSteps,
  shouldEmphasizeApiKeyGuide,
  DEFAULT_CONNECTION_LABEL,
  connectionLabelFollowsDb,
  nextConnectionLabel,
} from "./connect-checklist";

describe("connect-checklist", () => {
  it("tracks Online connect steps and suggests db", () => {
    const empty = buildConnectChecklist({
      url: "",
      dbName: "",
      username: "",
      password: "",
    });
    expect(empty.completed).toBe(0);

    const mid = buildConnectChecklist({
      url: "https://experiment-company.odoo.com/odoo",
      dbName: "experiment-company",
      username: "admin@example.com",
      password: "",
    });
    expect(mid.kind).toBe("online");
    expect(mid.steps.find((s) => s.id === "url")?.done).toBe(true);
    expect(mid.steps.find((s) => s.id === "database")?.done).toBe(true);
    expect(mid.steps.find((s) => s.id === "secret")?.done).toBe(false);
    expect(mid.steps.find((s) => s.id === "secret")?.emphasis).toBe("warn");

    const done = buildConnectChecklist({
      url: "https://experiment-company.odoo.com",
      dbName: "experiment-company",
      username: "admin@example.com",
      password: "key",
      verified: true,
    });
    expect(done.completed).toBe(done.total);
  });

  it("warns when Online db diverges from subdomain", () => {
    const c = buildConnectChecklist({
      url: "https://acme.odoo.com",
      dbName: "wrong",
      username: "a",
      password: "b",
    });
    expect(c.steps.find((s) => s.id === "database")?.emphasis).toBe("warn");
  });

  it("credential copy is Online-honest about API keys", () => {
    expect(credentialFieldCopy("online").hint).toMatch(/API key/i);
    expect(credentialFieldCopy("self_hosted").hint).toMatch(/password/i);
    expect(hostCapabilityBullets("online").some((b) => /Python/i.test(b))).toBe(true);
  });

  it("API key copy distinguishes Odoo RPC from Cursor MCP", () => {
    const online = credentialFieldCopy("online").hint;
    expect(online).toMatch(/XML-RPC|JSON-RPC|external RPC/i);
    expect(online).toMatch(/not a Cursor MCP|not.*Cursor MCP/i);
    expect(online).toMatch(/Model Context Protocol/i);
    const steps = apiKeyGuideSteps("online");
    const last = steps[steps.length - 1]?.body || "";
    expect(last).toMatch(/XML-RPC|JSON-RPC|external.?RPC/i);
    expect(last).toMatch(/not a Cursor MCP/i);
    const rpcStep = steps.find((s) => /RPC vs MCP/i.test(s.title));
    expect(rpcStep?.body).toMatch(/RPC|external API/i);
    expect(rpcStep?.body).toMatch(/Do not pick MCP|not.*MCP/i);
    expect(last).toMatch(/drafts|projects|history/i);
    expect(hostCapabilityBullets("online").some((b) => /not Cursor MCP/i.test(b))).toBe(true);
  });

  it("augments Online auth failures", () => {
    const msg = formatAuthFailureHint("online", "Authentication failed");
    expect(msg).toMatch(/API key/i);
    expect(formatAuthFailureHint("self_hosted", "timeout")).toBe("timeout");
  });
});

  it("API key guide is emphasized for Online and auth errors", () => {
    expect(shouldEmphasizeApiKeyGuide("online")).toBe(true);
    expect(shouldEmphasizeApiKeyGuide("self_hosted")).toBe(false);
    expect(shouldEmphasizeApiKeyGuide("self_hosted", "Authentication failed")).toBe(true);
    expect(apiKeyGuideSteps("online").length).toBeGreaterThanOrEqual(4);
  });

  it("auto-syncs Label from Database until the user edits Label", () => {
    expect(connectionLabelFollowsDb(DEFAULT_CONNECTION_LABEL, "odoo_dev")).toBe(true);
    expect(connectionLabelFollowsDb("odoo_dev", "odoo_dev")).toBe(true);
    expect(connectionLabelFollowsDb("Prod", "odoo_dev")).toBe(false);
    expect(
      nextConnectionLabel(DEFAULT_CONNECTION_LABEL, "odoo_dev", "experiment-company"),
    ).toBe("experiment-company");
    expect(nextConnectionLabel("Prod", "odoo_dev", "experiment-company")).toBe("Prod");
    expect(nextConnectionLabel("odoo_dev", "odoo_dev", "acme")).toBe("acme");
  });


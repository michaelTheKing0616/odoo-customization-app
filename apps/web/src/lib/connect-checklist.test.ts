import { describe, expect, it } from "vitest";
import {
  buildConnectChecklist,
  credentialFieldCopy,
  formatAuthFailureHint,
  hostCapabilityBullets,
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

  it("augments Online auth failures", () => {
    const msg = formatAuthFailureHint("online", "Authentication failed");
    expect(msg).toMatch(/API key/i);
    expect(formatAuthFailureHint("self_hosted", "timeout")).toBe("timeout");
  });
});

import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  classifyConnectError,
  connectErrorGuide,
  connectHonestyGuide,
  connectObserverNote,
  connectSecretTip,
  connectedGuide,
  emptyConnectGuide,
  hasEmOrEnDash,
  probeStageLabel,
  resolveConnectStep,
  sanitizeConnectCopy,
} from "./connectScreen";

describe("connectScreen", () => {
  it("keeps Add connection as the primary CTA copy", () => {
    expect(PRIMARY_CTA).toBe("Add connection");
  });

  it("strips em and en dashes", () => {
    expect(sanitizeConnectCopy("URL — then probe")).toBe("URL - then probe");
    expect(sanitizeConnectCopy("a–b")).toBe("a-b");
  });

  it("resolves stages from step and saving", () => {
    expect(resolveConnectStep({ step: 1, saving: false })).toBe("credentials");
    expect(resolveConnectStep({ step: 1, saving: true })).toBe("probe");
    expect(resolveConnectStep({ step: 2, saving: true })).toBe("probe");
    expect(resolveConnectStep({ step: 3, saving: false })).toBe("summary");
  });

  it("observer note is one line for chrome, not a twin banner", () => {
    const note = connectObserverNote();
    expect(note.toLowerCase()).toContain("observer");
    expect(note.length).toBeLessThan(140);
    expect(hasEmOrEnDash(note)).toBe(false);
  });

  it("secret tip only for Online (risk-gated)", () => {
    expect(connectSecretTip(true)).toMatch(/API key/i);
    expect(connectSecretTip(false)).toBeNull();
  });

  it("full honesty guide still available for docs/tests", () => {
    const g = connectHonestyGuide();
    expect(g.title.toLowerCase()).toContain("observer");
    expect(hasEmOrEnDash(g.title + g.why + g.next)).toBe(false);
  });

  it("empty guide points at Add connection", () => {
    const g = emptyConnectGuide();
    expect(g.next).toMatch(/Add connection/);
    expect(hasEmOrEnDash(g.title + g.why + g.next)).toBe(false);
  });

  it("connected guide prefers App Studio next", () => {
    const g = connectedGuide({ serverVersion: "19.0", capsMessage: "GA ready." });
    expect(g.title.toLowerCase()).toContain("connected");
    expect(g.why).toMatch(/19\.0/);
    expect(g.next).toMatch(/App Studio/);
  });

  it("probe stages advance with elapsed time", () => {
    expect(probeStageLabel(0)).toMatch(/Reaching/i);
    expect(probeStageLabel(950)).toMatch(/version/i);
    expect(probeStageLabel(2000)).toMatch(/rights/i);
  });

  it("classifies and guides common probe failures", () => {
    expect(classifyConnectError("getaddrinfo ENOTFOUND")).toBe("dns");
    expect(classifyConnectError("Two-factor authentication required")).toBe("two_factor");
    expect(classifyConnectError("HTTP 403 Forbidden")).toBe("ip_blocked");
    expect(classifyConnectError('database "acme" does not exist')).toBe("db_missing");
    expect(classifyConnectError("certificate has expired")).toBe("tls");
    expect(classifyConnectError("Authentication failed")).toBe("auth");
    expect(classifyConnectError("duplicate key")).toBe("duplicate");
    expect(classifyConnectError("ECONNREFUSED")).toBe("network");

    const auth = connectErrorGuide("auth", "Authentication failed");
    expect(auth.next.toLowerCase()).toMatch(/api key/);
    expect(hasEmOrEnDash(auth.title + auth.why + auth.next)).toBe(false);
  });
});

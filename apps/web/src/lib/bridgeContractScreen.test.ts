import { describe, expect, it } from "vitest";
import {
  EMPTY_FORM,
  PRIMARY_CTA,
  buildContract,
  classifyResult,
  firstErrorField,
  formsEqual,
  honestyGuide,
  networkErrorGuide,
  previewJson,
  sanitizeCopy,
  stepStates,
  validateForm,
  buildLedger,
  ledgerSummary,
  statusChip,
  overwriteRisk,
  HONESTY_LINE,
  type ContractForm,
} from "./bridgeContractScreen";

const FILLED: ContractForm = {
  odooId: "odoo-main",
  thirdId: "shopify-store",
  direction: "inbound",
  conflict: "",
  money: true,
  moneyPolicy: "odoo_wins",
};

const ALL_COPY = (): string[] => {
  const g = [honestyGuide(), networkErrorGuide(502), networkErrorGuide()];
  const outcomes = [
    classifyResult({ ok: true, tier: "I", direction: "two_way", entities: 2 }),
    classifyResult({ ok: false, tier: "I", error: "odoo and third-party connections must differ" }),
    classifyResult({ ok: false, tier: "I", error: "two_way requires conflict_resolution" }),
    classifyResult({ ok: false, tier: "I", error: "entity orders requires money_policy" }),
    classifyResult({ ok: false, tier: "I", error: "secrets belong on the Connection, not in the contract: token" }),
    classifyResult({ ok: false, tier: "I", error: "something else" }),
  ];
  return [PRIMARY_CTA, ...g.flatMap((x) => [x.title, x.why, x.next]), ...outcomes.flatMap((o) => [o.guide.title, o.guide.why, o.guide.next])];
};

describe("bridgeContractScreen", () => {
  it("copy carries no em or en dashes and no hype words", () => {
    for (const line of ALL_COPY()) {
      expect(line).not.toMatch(/[\u2014\u2013]/);
      expect(line).not.toMatch(/\b(seamless|elevate|unleash|oops|magic)\b/i);
    }
    expect(sanitizeCopy("a \u2014 b \u2013 c")).toBe("a - b - c");
  });

  it("honesty says validate does not connect, send, or write", () => {
    const g = honestyGuide();
    expect(g.title).toMatch(/does not connect or send/i);
    expect(g.why).toMatch(/no session/);
    expect(g.why).toMatch(/no webhook/);
    expect(g.why).toMatch(/writes nothing to Odoo/);
  });

  it("validateForm writes per-field instructions", () => {
    expect(validateForm(EMPTY_FORM)).toEqual({
      odooId: "Enter the Odoo connection id.",
      thirdId: "Enter the third-party connection id.",
    });
    expect(validateForm({ ...FILLED, thirdId: " odoo-main " }).thirdId).toMatch(/different connection/);
    expect(validateForm({ ...FILLED, direction: "two_way" }).conflict).toMatch(/Choose who wins/);
    expect(validateForm({ ...FILLED, direction: "two_way", conflict: "manual" })).toEqual({});
    expect(firstErrorField({ conflict: "x", thirdId: "y" })).toBe("thirdId");
    expect(firstErrorField({})).toBeNull();
  });

  it("buildContract sends ids only and conflict only for two-way", () => {
    const inbound = buildContract({ ...FILLED, odooId: "  odoo-main " });
    expect(inbound).toEqual({
      odoo_connection_id: "odoo-main",
      third_party_connection_id: "shopify-store",
      direction: "inbound",
      webhook_signature_required: true,
      entities: [{ name: "orders", money: true, money_policy: "odoo_wins" }],
    });
    expect("conflict_resolution" in inbound).toBe(false);
    const twoWay = buildContract({ ...FILLED, direction: "two_way", conflict: "remote_wins", money: false });
    expect(twoWay.conflict_resolution).toBe("remote_wins");
    expect((twoWay.entities as { money_policy: unknown }[])[0].money_policy).toBeNull();
    expect(previewJson(FILLED)).not.toMatch(/password|token|secret|api_key/i);
    expect(JSON.parse(previewJson(FILLED)).contract.direction).toBe("inbound");
  });

  it("stepStates is linear and derived from the form", () => {
    expect(stepStates(EMPTY_FORM, false)).toEqual({
      connections: "current",
      direction: "todo",
      money: "todo",
      validate: "todo",
    });
    expect(stepStates({ ...FILLED, direction: "two_way" }, false)).toEqual({
      connections: "done",
      direction: "current",
      money: "todo",
      validate: "todo",
    });
    expect(stepStates(FILLED, false).validate).toBe("current");
    // A Tier I refusal blames a step; it is never shown as done.
    expect(stepStates(FILLED, false, "connections")).toEqual({
      connections: "blocked",
      direction: "todo",
      money: "todo",
      validate: "todo",
    });
    expect(stepStates(FILLED, false, "money").money).toBe("blocked");
    expect(stepStates(FILLED, true)).toEqual({
      connections: "done",
      direction: "done",
      money: "done",
      validate: "done",
    });
  });

  it("classifies a pass without claiming a sync", () => {
    const o = classifyResult({ ok: true, tier: "I", direction: "two_way", entities: 1 });
    expect(o.kind).toBe("passed");
    expect(o.guide.title).toBe("Tier I passed for two-way");
    expect(o.guide.why).toMatch(/1 entity checked/);
    expect(o.guide.next).toMatch(/Nothing has synced/);
  });

  it("explains unverified connections by side and status", () => {
    const o = classifyResult({
      ok: false,
      tier: "I",
      error:
        "Tier I requires verified connections (verified_at set): odoo:odoo-main (missing), third_party:shop-1 (failed)",
    });
    expect(o.kind).toBe("refused");
    expect(o.guide.title).toBe("Connections are not verified");
    expect(o.guide.why).toBe(
      "Odoo connection odoo-main was not found. Third-party connection shop-1 is failed.",
    );
    expect(o.guide.next).toMatch(/Run Verify/);
    expect(o.kind === "refused" && o.step).toBe("connections");
  });

  it("maps field-level refusals back to the field", () => {
    const differ = classifyResult({ ok: false, tier: "I", error: "odoo and third-party connections must differ" });
    expect(differ.kind === "refused" && differ.field).toBe("thirdId");
    const conflict = classifyResult({ ok: false, tier: "I", error: "two_way requires conflict_resolution" });
    expect(conflict.kind === "refused" && conflict.field).toBe("conflict");
    const money = classifyResult({ ok: false, tier: "I", error: "entity orders requires money_policy" });
    expect(money.kind === "refused" && money.field).toBe("moneyPolicy");
    const secret = classifyResult({ ok: false, tier: "I", error: "secrets belong on the Connection, not in the contract: token" });
    expect(secret.guide.title).toBe("The contract carries a secret");
    const other = classifyResult({ ok: false, tier: "I", error: "" });
    expect(other.guide.why).toBe("The check returned no reason.");
  });

  it("network guide keeps entries and names the status", () => {
    expect(networkErrorGuide(502).why).toMatch(/HTTP 502/);
    expect(networkErrorGuide().next).toMatch(/entries are kept/);
  });

  it("buildLedger evaluates local rows live and server rows only from Tier I", () => {
    const idle = buildLedger(FILLED, null, { stale: false, pending: false });
    expect(idle.map((r) => r.status)).toEqual(["pass", "na", "pass", "pass", "pass", "wait", "wait"]);
    expect(ledgerSummary(idle)).toEqual({ passed: 4, applicable: 6, failed: 0 });
    const pending = buildLedger(FILLED, null, { stale: false, pending: true });
    expect(pending[5].detail).toBe("Checking…");
    const refused = classifyResult({
      ok: false,
      tier: "I",
      error: "Tier I requires verified connections (verified_at set): odoo:odoo-main (missing)",
    });
    const rows = buildLedger(FILLED, refused, { stale: false, pending: false });
    expect(rows[5]).toMatchObject({ status: "fail", detail: "Not found" });
    expect(rows[6]).toMatchObject({ status: "pass" });
    const staleRows = buildLedger(FILLED, refused, { stale: true, pending: false });
    expect(staleRows[5]).toMatchObject({ status: "wait", detail: "Validate again" });
    const same = buildLedger({ ...FILLED, thirdId: "odoo-main" }, null, { stale: false, pending: false });
    expect(same[0].status).toBe("fail");
    const secret = classifyResult({ ok: false, tier: "I", error: "secrets belong on the Connection, not in the contract: token" });
    expect(buildLedger(FILLED, secret, { stale: false, pending: false })[4].status).toBe("fail");
    const err = { kind: "error" as const, guide: networkErrorGuide(502) };
    expect(buildLedger(FILLED, err, { stale: false, pending: false })[5].status).toBe("skip");
  });

  it("statusChip and overwriteRisk stay honest", () => {
    expect(statusChip(null, { stale: false, pending: false })).toEqual({ label: "Draft", tone: "neutral" });
    expect(statusChip(null, { stale: false, pending: true }).label).toBe("Checking");
    const pass = classifyResult({ ok: true, tier: "I", direction: "inbound", entities: 1 });
    expect(statusChip(pass, { stale: false, pending: false }).tone).toBe("success");
    expect(statusChip(pass, { stale: true, pending: false }).label).toBe("Edited since check");
    expect(overwriteRisk(FILLED)).toBeNull();
    expect(overwriteRisk({ ...FILLED, moneyPolicy: "remote_wins" })).toMatch(/overwrite Odoo order totals/);
    expect(overwriteRisk({ ...FILLED, money: false, moneyPolicy: "remote_wins" })).toBeNull();
    expect(overwriteRisk({ ...FILLED, direction: "two_way", conflict: "remote_wins" })).toMatch(/replace Odoo edits/);
    expect(HONESTY_LINE).toBe("Read-only check. Nothing connects, sends, or syncs.");
  });

  it("formsEqual compares every field", () => {
    expect(formsEqual(FILLED, { ...FILLED })).toBe(true);
    expect(formsEqual(FILLED, { ...FILLED, money: false })).toBe(false);
  });
});

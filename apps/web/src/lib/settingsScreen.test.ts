import { describe, expect, it } from "vitest";
import {
  BOOTSTRAP_CTA,
  PRIMARY_CTA,
  SAVE_CTA,
  bootstrapSettingsGuide,
  createBlockedReason,
  emptySettingsGuide,
  idleSettingsGuide,
  revealedSettingsGuide,
  sanitizeSettingsCopy,
  savedBrowserGuide,
  settingsErrorGuide,
  settingsHonestyGuide,
  settingsStepFromState,
} from "@/lib/settingsScreen";

describe("settingsScreen", () => {
  it("names Create API key as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Create API key");
    expect(BOOTSTRAP_CTA).toBe("Generate first API key");
    expect(SAVE_CTA).toBe("Save in browser");
  });

  it("steps Status → Keys → Audit from state", () => {
    expect(
      settingsStepFromState({
        hasStatus: true,
        keysListed: false,
        keyCount: 0,
        revealed: false,
        auditHydrated: false,
      }),
    ).toBe(1);
    expect(
      settingsStepFromState({
        hasStatus: true,
        keysListed: true,
        keyCount: 2,
        revealed: false,
        auditHydrated: true,
      }),
    ).toBe(2);
    expect(
      settingsStepFromState({
        hasStatus: true,
        keysListed: true,
        keyCount: 0,
        revealed: true,
        auditHydrated: true,
      }),
    ).toBe(2);
    expect(
      settingsStepFromState({
        hasStatus: true,
        keysListed: true,
        keyCount: 0,
        revealed: false,
        auditHydrated: true,
      }),
    ).toBe(3);
  });

  it("guides cover what/why/next without em dashes", () => {
    const guides = [
      settingsHonestyGuide(),
      emptySettingsGuide(),
      idleSettingsGuide(),
      bootstrapSettingsGuide(),
      revealedSettingsGuide(),
      savedBrowserGuide(false),
      savedBrowserGuide(true),
      settingsErrorGuide("load", "timed out"),
      settingsErrorGuide("create", "forbidden"),
    ];
    for (const g of guides) {
      const blob = `${g.title} ${g.why} ${g.next}`;
      expect(blob).not.toMatch(/[\u2014\u2013]/);
      expect(g.why.length).toBeGreaterThan(10);
      expect(g.next.length).toBeGreaterThan(10);
    }
  });

  it("honesty states browser save and one-time reveal", () => {
    const h = settingsHonestyGuide();
    expect(h.title.toLowerCase()).toMatch(/shown once|this device/);
    expect(h.why.toLowerCase()).toMatch(/localstorage|shown once|revoke/);
    const revealed = revealedSettingsGuide();
    expect(revealed.title.toLowerCase()).toMatch(/copy now|shown once/);
  });

  it("blocks create when busy, auth off, or no browser key", () => {
    expect(
      createBlockedReason({ busy: true, authEnabled: true, hasBrowserKey: true }),
    ).toMatch(/Wait/);
    expect(
      createBlockedReason({ busy: false, authEnabled: false, hasBrowserKey: true }),
    ).toMatch(/auth/i);
    expect(
      createBlockedReason({ busy: false, authEnabled: true, hasBrowserKey: false }),
    ).toMatch(/browser key|bootstrap/i);
    expect(
      createBlockedReason({ busy: false, authEnabled: true, hasBrowserKey: true }),
    ).toBeNull();
  });

  it("sanitizes em dashes", () => {
    expect(sanitizeSettingsCopy("a\u2014b\u2013c")).toBe("a-b-c");
  });
});

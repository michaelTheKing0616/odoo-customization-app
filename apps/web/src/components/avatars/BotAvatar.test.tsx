/** @vitest-environment happy-dom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BotAvatar, BotPresenceChip } from "./BotAvatar";
import {
  BOT_ROLES,
  BOT_STATES,
  accentColor,
  displayName,
  expertMorphWeights,
  previewSrc,
  resolveClip,
} from "@/lib/avatars/playback";

vi.mock("next/dynamic", () => ({
  default: () => () => null,
}));

afterEach(() => {
  cleanup();
});

describe("avatar contract playback", () => {
  it("names all 14 roles and a preview for light and navy", () => {
    expect(BOT_ROLES).toHaveLength(14);
    for (const role of BOT_ROLES) {
      expect(displayName(role)).toMatch(/^Ingenium Bot · /);
      expect(previewSrc(role, "light")).toBe(`/avatars/ingenium/${role}_light.png`);
      expect(previewSrc(role, "navy")).toBe(`/avatars/ingenium/${role}_navy.png`);
    }
  });

  it("loops and plays once according to the contract, including expert listening", () => {
    for (const role of BOT_ROLES) {
      for (const state of BOT_STATES) {
        const resolved = resolveClip(role, state);
        if (state === "listening" || state === "speaking") {
          if (role === "expert") expect(resolved).toEqual({ clip: state, loop: true });
          else expect(resolved.clip).toBe("idle");
        }
      }
    }
    expect(resolveClip("access", "done")).toEqual({ clip: "done", loop: false });
    expect(resolveClip("access", "working")).toEqual({ clip: "working", loop: true });
    expect(resolveClip("studio", "acknowledged").loop).toBe(false);
  });

  it("stops handing out WebGL slots at the budget", async () => {
    const { acquireAvatarGl, releaseAvatarGl } = await import("@/lib/avatars/playback");
    const claimed: boolean[] = [];
    for (let i = 0; i < 14; i += 1) claimed.push(acquireAvatarGl());
    expect(claimed.filter(Boolean)).toHaveLength(12);
    for (let i = 0; i < 12; i += 1) releaseAvatarGl();
  });

  it("tints only the specialist from config and drives expert morphs", () => {
    expect(accentColor("specialist", "#112233")).toBe("#112233");
    expect(accentColor("specialist", "not-a-color")).toBe("#B08CE0");
    expect(accentColor("ops", "#112233")).toBe("#F2CE1B");
    expect(expertMorphWeights("expert", "blocked", 0.4, 1)).toMatchObject({
      blink: 1,
      browDown: 0.7,
      mouthOpen: 0.4,
    });
    expect(expertMorphWeights("scribe", "speaking", 1, 1).mouthOpen).toBe(0);
  });
});

describe("BotAvatar fallback", () => {
  it("uses the preview at 32px and in the presence chip", () => {
    render(<BotAvatar role="expert" state="thinking" size={32} />);
    const frame = screen.getByRole("img", { name: "Ingenium Bot · AI Expert: thinking" });
    expect(frame).toHaveAttribute("data-bot-mode", "preview");
    expect(frame.querySelector("img")).toHaveAttribute("src", "/avatars/ingenium/expert_light.png");
    cleanup();
    render(<BotPresenceChip role="chief_of_staff" state="waiting_approval" />);
    expect(screen.getByRole("img", { name: "Ingenium Bot · Chief of Staff: waiting for approval" })).toHaveAttribute(
      "data-bot-mode",
      "preview",
    );
  });

  it("stays on the preview when motion is reduced, even above 32px", async () => {
    const original = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    render(<BotAvatar role="data" state="idle" size={64} />);
    expect(screen.getByRole("img")).toHaveAttribute("data-bot-mode", "preview");
    expect(screen.getByRole("img").querySelector("img")).toHaveAttribute("src", "/avatars/ingenium/data_light.png");
    window.matchMedia = original;
  });
});

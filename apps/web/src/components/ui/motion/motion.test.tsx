/** @vitest-environment jsdom */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import {
  DURATION,
  DURATION_RANGE,
  EASE_DRAWER,
  EASE_ENTER_EXIT,
  EXIT_RATIO,
  PRESS_SCALE,
  REDUCED_MOTION_MAX_MS,
  REDUCED_MOTION_QUERY,
  exitDurationMs,
} from "./constants";
import {
  DRAWER_INTERRUPTIBLE,
  drawerAnimateForOpen,
  drawerOpenTarget,
  listItemInitial,
  listItemRest,
  motionKeys,
  panelTransition,
  readPrefersReducedMotion,
  resolveMotionStyle,
  resolvePanelAnimate,
} from "./resolve";
import { Drawer } from "./Drawer";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubMatchMedia(reduced: boolean) {
  const matchMedia = (query: string) => ({
    matches: reduced && query === REDUCED_MOTION_QUERY,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  });
  vi.stubGlobal("matchMedia", matchMedia);
  window.matchMedia = matchMedia as typeof window.matchMedia;
}

describe("UI-F09 motion constants", () => {
  it("reads durations and easings from the single constants module", () => {
    expect(DURATION.pressMs).toBeGreaterThanOrEqual(DURATION_RANGE.pressMs.min);
    expect(DURATION.pressMs).toBeLessThanOrEqual(DURATION_RANGE.pressMs.max);
    expect(DURATION.dropdownMs).toBeGreaterThanOrEqual(DURATION_RANGE.dropdownMs.min);
    expect(DURATION.dropdownMs).toBeLessThanOrEqual(DURATION_RANGE.dropdownMs.max);
    expect(DURATION.modalMs).toBeGreaterThanOrEqual(DURATION_RANGE.modalMs.min);
    expect(DURATION.modalMs).toBeLessThanOrEqual(DURATION_RANGE.modalMs.max);
    expect(DURATION.drawerMs).toBeGreaterThanOrEqual(DURATION_RANGE.modalMs.min);
    expect(DURATION.drawerMs).toBeLessThanOrEqual(DURATION_RANGE.modalMs.max);
    expect(DURATION.staggerMs).toBeGreaterThanOrEqual(DURATION_RANGE.staggerMs.min);
    expect(DURATION.staggerMs).toBeLessThanOrEqual(DURATION_RANGE.staggerMs.max);
    expect(DURATION.reducedMotionMs).toBeLessThanOrEqual(REDUCED_MOTION_MAX_MS);
    expect(exitDurationMs(DURATION.modalMs)).toBe(Math.round(DURATION.modalMs * EXIT_RATIO));
    expect(exitDurationMs(DURATION.drawerMs)).toBe(Math.round(DURATION.drawerMs * EXIT_RATIO));
    expect(PRESS_SCALE).toBeLessThan(1);
    expect(EASE_ENTER_EXIT.css).toMatch(/^cubic-bezier\(/);
    expect(EASE_DRAWER.css).toMatch(/^cubic-bezier\(/);
    expect(EASE_ENTER_EXIT.bezier).toHaveLength(4);
    expect(EASE_DRAWER.bezier).toHaveLength(4);
  });
});

describe("UI-F09 reduced motion", () => {
  it("mocks matchMedia and keeps opacity only (no transform or scale)", () => {
    stubMatchMedia(true);
    expect(readPrefersReducedMotion()).toBe(true);

    const open = resolvePanelAnimate(true, "right", true);
    const closed = resolvePanelAnimate(false, "right", true);
    const fromFull = resolveMotionStyle({ opacity: 1, x: "40%", scale: PRESS_SCALE, y: 8 }, true);
    const listEnter = listItemInitial(true);
    const listRest = listItemRest(true);

    expect(motionKeys(open)).toEqual(["opacity", "x"]);
    expect(motionKeys(closed)).toEqual(["opacity", "x"]);
    expect(open.x).toBe(0);
    expect(closed.x).toBe(0);
    expect(motionKeys(fromFull)).toEqual(["opacity"]);
    expect(motionKeys(listEnter)).toEqual(["opacity"]);
    expect(motionKeys(listRest)).toEqual(["opacity"]);
    expect(open).not.toHaveProperty("y");
    expect(open).not.toHaveProperty("scale");
    expect(fromFull).not.toHaveProperty("scale");

    const transition = panelTransition(true, true);
    expect(transition.duration).toBeLessThanOrEqual(REDUCED_MOTION_MAX_MS / 1000);
  });
});

describe("UI-F09 interruptible drawer", () => {
  it("close target is independent of the in-progress value (exit starts from current)", () => {
    expect(DRAWER_INTERRUPTIBLE.remountOnToggle).toBe(false);
    expect(DRAWER_INTERRUPTIBLE.resetInitialOnClose).toBe(false);

    const inProgress = { x: "42%", opacity: 0.58 };
    const closeTarget = drawerAnimateForOpen(false, "right");
    expect(closeTarget).toEqual({ x: "100%", opacity: 0 });
    expect(closeTarget).not.toEqual(inProgress);
    expect(closeTarget).not.toEqual(drawerOpenTarget());
    expect(panelTransition(false, false).type).toBe("tween");
  });

  it("keeps the same drawer panel node when open flips to closed", () => {
    const { rerender } = render(
      <Drawer open={true} onOpenChange={() => undefined} title="Queue">
        Body
      </Drawer>,
    );
    const panel = screen.getByTestId("motion-drawer-panel");
    rerender(
      <Drawer open={false} onOpenChange={() => undefined} title="Queue">
        Body
      </Drawer>,
    );
    expect(screen.getByTestId("motion-drawer-panel")).toBe(panel);
    expect(screen.getByTestId("motion-drawer").getAttribute("data-interruptible")).toBe("true");
  });

  it("renders opacity only on the open panel when reduced motion is set", () => {
    stubMatchMedia(true);
    render(
      <Drawer open onOpenChange={() => undefined} title="Queue">
        Body
      </Drawer>,
    );
    const panel = screen.getByTestId("motion-drawer-panel");
    expect(panel).toHaveAttribute("data-motion-keys", "opacity x");
    expect(panel.getAttribute("style") ?? "").not.toMatch(/scale/i);
  });

  it("reverses from the in-progress x when closed before the open tween finishes", async () => {
    stubMatchMedia(false);
    const originalDrawerMs = DURATION.drawerMs;
    (DURATION as { drawerMs: number }).drawerMs = 2000;
    try {
      const { rerender } = render(
        <Drawer open={false} onOpenChange={() => undefined} title="Queue">
          Body
        </Drawer>,
      );
      rerender(
        <Drawer open onOpenChange={() => undefined} title="Queue">
          Body
        </Drawer>,
      );
      const panel = screen.getByTestId("motion-drawer-panel");
      let mid = Number.NaN;
      await waitFor(() => {
        mid = Number.parseFloat(String(panel.dataset.motionX));
        expect(mid).toBeGreaterThan(5);
        expect(mid).toBeLessThan(95);
      });

      rerender(
        <Drawer open={false} onOpenChange={() => undefined} title="Queue">
          Body
        </Drawer>,
      );
      await waitFor(() => {
        const after = Number.parseFloat(String(panel.dataset.motionX));
        expect(after).toBeGreaterThan(mid);
      });
    } finally {
      (DURATION as { drawerMs: number }).drawerMs = originalDrawerMs;
    }
  });
});

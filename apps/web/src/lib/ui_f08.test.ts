/**
 * Oracle tests for UI-F08 (Sonner everywhere). Locked contract for AppToaster behavior.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import React, { act } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { AppToaster, APP_TOAST_DURATION_MS } from "@/components/ui/AppToaster";

const WEB_SRC = join(__dirname, "..");

function walkUiSources(): string[] {
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const n of readdirSync(dir)) {
      const p = join(dir, n);
      if (statSync(p).isDirectory()) walk(p);
      else if (/\.(tsx?|jsx?)$/.test(n) && !/\.test\./.test(n)) out.push(p);
    }
  };
  walk(join(WEB_SRC, "components", "ui"));
  walk(join(WEB_SRC, "components", "shell"));
  return out;
}

describe("UI-F08 Sonner", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("test_ac1_no_legacy_toast_component_in_shell_or_ui", () => {
    const legacy = walkUiSources().filter((f) => {
      const s = readFileSync(f, "utf8");
      return (
        s.includes('from "@/components/ui/Toast"') ||
        s.includes("components/ui/Toast") ||
        s.includes("useToast(")
      );
    });
    expect(legacy).toEqual([]);
    expect(() => readFileSync(join(WEB_SRC, "components", "ui", "Toast.tsx"), "utf8")).toThrow();
  });

  it("test_ac2_polite_live_region_and_success_duration_band", () => {
    expect(APP_TOAST_DURATION_MS).toBeGreaterThanOrEqual(3000);
    expect(APP_TOAST_DURATION_MS).toBeLessThanOrEqual(5000);

    const { container } = render(React.createElement(AppToaster));
    expect(container.querySelector('section[aria-live="polite"]')).not.toBeNull();
  });

  it("test_ac3_toast_tsx_removed", () => {
    const uiDir = join(WEB_SRC, "components", "ui");
    expect(readdirSync(uiDir).includes("Toast.tsx")).toBe(false);
  });

  it("test_ac4_error_toast_still_visible_after_10s", async () => {
    render(
      React.createElement(
        React.Fragment,
        null,
        React.createElement(AppToaster),
        React.createElement(
          "button",
          { type: "button", onClick: () => toast.error("Persisted error") },
          "Fire error",
        ),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Fire error" }));
    await waitFor(() => expect(screen.getAllByText("Persisted error").length).toBeGreaterThan(0));

    vi.useFakeTimers();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(screen.getAllByText("Persisted error").length).toBeGreaterThan(0);
  });
});

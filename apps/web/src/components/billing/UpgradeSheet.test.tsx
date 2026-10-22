/** @vitest-environment jsdom */
import React, { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UpgradeSheet, upgradeSheetDescription } from "./UpgradeSheet";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api", () => ({
  api: {
    billingEntitlements: vi.fn().mockResolvedValue({
      workspace_id: "w1",
      plan_id: "free_solo",
      subscription_status: "active",
      features: {},
      extra_project_slots: 0,
      active_projects: 1,
      active_project_limit: 1,
      trial_ends_at: null,
      current_period_end: null,
    }),
    billingPlans: vi.fn().mockResolvedValue({
      tier_order: ["free_solo", "pro"],
      display_features: [],
      project_pass: { display_name: "Project Pass", one_time_usd: 49 },
      plans: [
        {
          id: "pro",
          display_name: "Pro",
          features: { expert: "true" },
          monthly_usd: 20,
          extra_slot_monthly_usd: 5,
        },
      ],
    }),
    stripeCheckout: vi.fn(),
    stripeExtraSlotsCheckout: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
});

function UpgradeHarness() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Open upgrade
      </button>
      <UpgradeSheet open={open} onOpenChange={setOpen} featureKey="expert" />
    </div>
  );
}

function expectUpgradeClosed() {
  expect(screen.queryByRole("dialog", { name: "Upgrade your plan" })).not.toBeInTheDocument();
}

describe("UpgradeSheet", () => {
  it("description is deterministic from featureKey (SSR == first client render)", () => {
    const pick = "Pick a plan. Operate tools (bulk, health checks, snapshots) stay available on every plan.";
    expect(upgradeSheetDescription(undefined)).toBe(pick);
    expect(upgradeSheetDescription(null)).toBe(pick);
    expect(upgradeSheetDescription("")).toBe(pick);
    expect(upgradeSheetDescription(undefined)).toBe(upgradeSheetDescription(undefined));
    expect(upgradeSheetDescription("designer")).toMatch(/^Unlock View designer\./);
  });

  it("opens and closes, and Escape and the backdrop dismiss it", async () => {
    render(<UpgradeHarness />);
    expectUpgradeClosed();

    fireEvent.click(screen.getByRole("button", { name: "Open upgrade" }));
    const dialog = await screen.findByRole("dialog", { name: "Upgrade your plan" });
    expect(screen.getByTestId("upgrade-sheet")).toContainElement(dialog);
    expect(screen.getByTestId("motion-sheet-panel")).toBe(dialog);
    expect(screen.getByRole("heading", { name: "Upgrade your plan" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upgrade to Pro" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Compare all plans" })).toHaveAttribute("href", "/pricing");

    fireEvent.click(screen.getByRole("button", { name: "Close panel" }));
    await waitFor(expectUpgradeClosed);

    fireEvent.click(screen.getByRole("button", { name: "Open upgrade" }));
    await screen.findByRole("dialog", { name: "Upgrade your plan" });
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(expectUpgradeClosed);

    fireEvent.click(screen.getByRole("button", { name: "Open upgrade" }));
    await screen.findByRole("dialog", { name: "Upgrade your plan" });
    const backdrop = screen.getByTestId("upgrade-sheet").querySelector('[class*="bg-black/40"]');
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop!);
    await waitFor(expectUpgradeClosed);
  });
});

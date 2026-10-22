/** @vitest-environment happy-dom */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const entitlements = vi.hoisted(() => ({
  state: {
    data: null as null | Record<string, unknown>,
    loading: true,
    refresh: () => undefined,
  } as {
    data: null | Record<string, unknown>;
    loading: boolean;
    refresh: () => void;
    error?: string | null;
    signedOut?: boolean;
  },
}));

vi.mock("@/components/billing/billing-desk.css", () => ({}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/useEntitlements", () => ({
  useEntitlements: () => entitlements.state,
}));
vi.mock("@/lib/upgrade-context", () => ({
  useUpgrade: () => ({ openUpgrade: vi.fn() }),
}));
vi.mock("@/lib/api", () => ({
  api: {
    billingPlanDiff: vi.fn(() => Promise.resolve({ from_plan: "pro", to_plan: "free_solo", lost_features: [] })),
    billingPlans: vi.fn(() =>
      Promise.resolve({
        tier_order: ["free_solo", "pro", "business", "agency"],
        display_features: [{ key: "bulk_suite", label: "Bulk suite" }],
        project_pass: { display_name: "Project Pass", one_time_usd: 299 },
        plans: [
          { id: "free_solo", display_name: "Free Solo", monthly_usd: 0, extra_slot_monthly_usd: null, features: {} },
          { id: "pro", display_name: "Pro", monthly_usd: 39, extra_slot_monthly_usd: 15, features: {} },
          { id: "business", display_name: "Business", monthly_usd: 149, extra_slot_monthly_usd: 10, features: {} },
          { id: "agency", display_name: "Agency", monthly_usd: 399, extra_slot_monthly_usd: null, features: {} },
        ],
      }),
    ),
    stripePortal: vi.fn(),
    stripeCheckout: vi.fn(),
  },
}));

import BillingSettingsPage from "./page";

afterEach(() => {
  cleanup();
});

describe("billing page states", () => {
  it("shows a plan-shaped skeleton while entitlements load", () => {
    entitlements.state = { data: null, loading: true, refresh: () => undefined };
    render(<BillingSettingsPage />);

    const loading = screen.getByTestId("billing-plan-loading");
    expect(loading).toHaveAttribute("role", "status");
    expect(screen.getByText("Loading your plan.")).toBeInTheDocument();
    expect(loading.querySelectorAll(".shimmer-15")).toHaveLength(5);
    expect(screen.queryByText(/Loading…|Loading\.\.\./)).toBeNull();
  });

  it("shows the empty state with a sign-in action when there is no plan", () => {
    entitlements.state = { data: null, loading: false, refresh: () => undefined };
    render(<BillingSettingsPage />);

    expect(screen.getByRole("heading", { name: "No plan to show" })).toBeInTheDocument();
    expect(
      screen.getByText("Your plan, status, and project slots appear here after you sign in with an account."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(screen.queryByTestId("billing-plan-loading")).toBeNull();
  });

  it("shows the sign-in empty state when the plan request is unauthorized", () => {
    entitlements.state = {
      data: null,
      loading: false,
      refresh: () => undefined,
      error: "Not authenticated",
      signedOut: true,
    };
    render(<BillingSettingsPage />);

    expect(screen.getByRole("heading", { name: "No plan to show" })).toBeInTheDocument();
    expect(screen.queryByTestId("billing-plan-error")).toBeNull();
  });

  it("shows an error with a retry instead of the empty state when the plan request fails", () => {
    const refresh = vi.fn();
    entitlements.state = {
      data: null,
      loading: false,
      refresh,
      error: "Request failed (500)",
      signedOut: false,
    };
    render(<BillingSettingsPage />);

    expect(screen.getByTestId("billing-plan-error")).toBeInTheDocument();
    expect(screen.getByText(/We couldn't load your plan\./)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "No plan to show" })).toBeNull();
    screen.getByRole("button", { name: "Try again" }).click();
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("shows the plan desk with Manage plan as the only teal primary and catalog prices", async () => {
    entitlements.state = {
      data: {
        workspace_id: "ws",
        plan_id: "pro",
        subscription_status: "active",
        features: { bulk_suite: "false" },
        extra_project_slots: 0,
        active_projects: 1,
        active_project_limit: 3,
        trial_ends_at: null,
        current_period_end: "2026-11-01T00:00:00Z",
      },
      loading: false,
      refresh: () => undefined,
    };
    const { container } = render(<BillingSettingsPage />);

    await waitFor(() => expect(screen.getByTestId("billing-plan-price")).toHaveTextContent("$39"));
    expect(container.querySelectorAll("button.bg-accent")).toHaveLength(1);
    expect(screen.getByTestId("billing-manage-plan")).toHaveTextContent("Manage plan");
    expect(screen.getByRole("button", { name: /Manage billing/ })).toBeInTheDocument();
    expect(screen.getByTestId("downgrade-summary")).toBeInTheDocument();
  });
});

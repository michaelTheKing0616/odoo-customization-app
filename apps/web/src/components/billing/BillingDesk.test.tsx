/** @vitest-environment happy-dom */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BillingPlansCatalog, EntitlementsOut } from "@/lib/api";
import { BillingDesk } from "./BillingDesk";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const CATALOG: BillingPlansCatalog = {
  tier_order: ["free_solo", "pro", "business", "agency"],
  display_features: [
    { key: "active_projects_limit", label: "Active projects" },
    { key: "bulk_suite", label: "Bulk suite" },
  ],
  project_pass: { display_name: "Project Pass", one_time_usd: 299 },
  plans: [
    { id: "free_solo", display_name: "Free Solo", monthly_usd: 0, extra_slot_monthly_usd: null, features: { active_projects_limit: "1", bulk_suite: "false" } },
    { id: "pro", display_name: "Pro", monthly_usd: 39, extra_slot_monthly_usd: 15, features: { active_projects_limit: "3", bulk_suite: "false" } },
    { id: "business", display_name: "Business", monthly_usd: 149, extra_slot_monthly_usd: 10, features: { active_projects_limit: "10", bulk_suite: "true" } },
    { id: "agency", display_name: "Agency", monthly_usd: 399, extra_slot_monthly_usd: null, features: { active_projects_limit: "25", bulk_suite: "true" } },
  ],
};

const NOW = Date.parse("2026-10-05T12:00:00Z");
const ent = (over: Partial<EntitlementsOut> = {}): EntitlementsOut => ({
  workspace_id: "ws_7f3a9c",
  plan_id: "pro",
  subscription_status: "active",
  features: { active_projects_limit: "5", bulk_suite: "false" },
  extra_project_slots: 2,
  active_projects: 3,
  active_project_limit: 5,
  trial_ends_at: null,
  current_period_end: "2026-10-29T00:00:00Z",
  ...over,
});

afterEach(cleanup);

function tealButtons(container: HTMLElement) {
  return container.querySelectorAll("button.bg-accent");
}

describe("BillingDesk", () => {
  it("paid plan: one teal Manage plan that opens the portal, real price, receipt math", () => {
    const onManagePlan = vi.fn();
    const { container } = render(
      <BillingDesk view="ready" data={ent()} catalog={CATALOG} now={NOW} onManagePlan={onManagePlan} />,
    );
    expect(tealButtons(container)).toHaveLength(1);
    const primary = screen.getByTestId("billing-manage-plan");
    expect(primary).toHaveTextContent("Manage plan");
    fireEvent.click(primary);
    expect(onManagePlan).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("billing-plan-price")).toHaveTextContent("$39");
    const charge = screen.getByTestId("billing-charge");
    expect(charge).toHaveTextContent("$69.00");
    expect(charge).toHaveTextContent("2 extra project slots at $15");
    expect(charge).toHaveTextContent("Stripe invoice is final");
    expect(screen.getByRole("button", { name: /Manage billing/ })).toBeInTheDocument();
    expect(screen.queryByTestId("trial-banner")).toBeNull();
    expect(screen.getByRole("meter", { name: "Active project slots used" })).toHaveAttribute("aria-valuenow", "3");
  });

  it("next tier column marks gains with a sign, not color alone", () => {
    render(<BillingDesk view="ready" data={ent()} catalog={CATALOG} now={NOW} />);
    const table = within(screen.getByTestId("billing-includes")).getByRole("table");
    const bulkRow = within(table).getByRole("row", { name: /Bulk suite/ });
    expect(bulkRow).toHaveTextContent("+");
    expect(bulkRow).toHaveTextContent("Gains");
  });

  it("free plan: Manage plan unfolds the chooser with real tier prices", () => {
    const onCheckout = vi.fn();
    render(
      <BillingDesk
        view="ready"
        data={ent({ plan_id: "free_solo", features: { active_projects_limit: "1" }, extra_project_slots: 0, active_project_limit: 1, active_projects: 0 })}
        catalog={CATALOG}
        now={NOW}
        onCheckout={onCheckout}
      />,
    );
    const primary = screen.getByTestId("billing-manage-plan");
    expect(primary).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(primary);
    expect(primary).toHaveAttribute("aria-expanded", "true");
    const chooser = screen.getByTestId("billing-plan-chooser");
    expect(chooser).toHaveTextContent("$149");
    fireEvent.click(within(chooser).getByRole("button", { name: "Continue with Pro" }));
    expect(onCheckout).toHaveBeenCalledWith("pro");
    expect(screen.queryByTestId("downgrade-summary")).toBeNull();
    expect(screen.getByTestId("billing-charge")).toHaveTextContent("No recurring charge");
  });

  it("trial: amber trial notice, downgrade preview, no fake scheduled charge", () => {
    render(
      <BillingDesk
        view="ready"
        data={ent({ plan_id: "business", subscription_status: "trialing", trial_ends_at: "2026-10-07T12:00:00Z", extra_project_slots: 0 })}
        catalog={CATALOG}
        lostFeatures={[{ feature_key: "bulk_suite", from: "true", to: "false" }]}
        now={NOW}
      />,
    );
    expect(screen.getByTestId("trial-banner")).toHaveTextContent("Trial ends in 2 days");
    expect(screen.getByTestId("downgrade-summary")).toHaveTextContent("Bulk suite");
    expect(screen.getByTestId("billing-charge")).toHaveTextContent("To keep Business");
    expect(screen.getByTestId("billing-charge")).toHaveTextContent("nothing is scheduled");
  });

  it("internal: Manage plan disabled with the reason, not billed", () => {
    render(
      <BillingDesk view="ready" data={ent({ plan_id: "internal", active_project_limit: null, extra_project_slots: 0 })} catalog={CATALOG} now={NOW} />,
    );
    expect(screen.getByTestId("billing-manage-plan")).toBeDisabled();
    expect(screen.getByText(/no Stripe subscription, so there is no plan to change/)).toBeInTheDocument();
    expect(screen.getByTestId("billing-charge")).toHaveTextContent("Not billed");
  });

  it("past due: danger notice with a payment action", () => {
    const onManageBilling = vi.fn();
    render(
      <BillingDesk view="ready" data={ent({ subscription_status: "past_due" })} catalog={CATALOG} now={NOW} onManageBilling={onManageBilling} />,
    );
    const risk = screen.getByTestId("billing-risk-payment");
    expect(risk).toHaveAttribute("role", "alert");
    fireEvent.click(within(risk).getByRole("button", { name: "Update payment method" }));
    expect(onManageBilling).toHaveBeenCalled();
  });

  it("portal error sits next to Manage billing with what, why, next", () => {
    render(
      <BillingDesk
        view="ready"
        data={ent({ plan_id: "business", subscription_status: "trialing", trial_ends_at: "2026-10-20T00:00:00Z" })}
        catalog={CATALOG}
        now={NOW}
        actionError={{ context: "portal", source: "billing", message: "No billing customer on file" }}
      />,
    );
    const payment = screen.getByTestId("billing-payment");
    const err = within(payment).getByTestId("billing-action-error");
    expect(err).toHaveTextContent("No Stripe customer on file yet");
    fireEvent.click(within(err).getByRole("button", { name: "Choose a plan" }));
    expect(screen.getByTestId("billing-plan-chooser")).toBeInTheDocument();
  });

  it("checkout return shows a status note with refresh", () => {
    const onRefresh = vi.fn();
    render(
      <BillingDesk view="ready" data={ent()} catalog={CATALOG} now={NOW} returned={{ upgraded: true }} onRefresh={onRefresh} />,
    );
    const note = screen.getByTestId("billing-return-note");
    expect(note).toHaveAttribute("role", "status");
    fireEvent.click(within(note).getByRole("button", { name: "Refresh plan" }));
    expect(onRefresh).toHaveBeenCalled();
  });

  it("missing catalog: price reads unavailable, never guessed", () => {
    render(<BillingDesk view="ready" data={ent()} catalog={null} now={NOW} />);
    expect(screen.getByTestId("billing-plan-price")).toHaveTextContent("Unavailable");
    expect(screen.getByTestId("billing-charge")).toHaveTextContent("no estimate is shown");
  });

  it("copy has no em dashes in any ready state", () => {
    const { container } = render(
      <BillingDesk view="ready" data={ent({ subscription_status: "past_due" })} catalog={CATALOG} now={NOW} returned={{ upgraded: true }} />,
    );
    expect(container.textContent).not.toMatch(/[—–]/);
  });
});

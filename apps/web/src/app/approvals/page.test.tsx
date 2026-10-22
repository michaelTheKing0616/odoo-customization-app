/** @vitest-environment happy-dom */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

vi.mock("@/components/plan-inbox/plan-inbox-operate.css", () => ({}));

import ApprovalsPage from "@/app/approvals/page";

const SECTIONS = [
  { title: "goal and assumptions", body: "SENTINEL_GOAL_BODY" },
  { title: "each change", body: "SENTINEL_CHANGE_BODY" },
  { title: "impact", body: "SENTINEL_IMPACT_BODY" },
  { title: "risk and why", body: "SENTINEL_RISK_BODY" },
  { title: "what is not changing", body: "SENTINEL_NOT_CHANGING_BODY" },
  { title: "how it will be checked", body: "SENTINEL_VERIFY_BODY" },
  { title: "how to undo", body: "SENTINEL_UNDO_BODY" },
  { title: "environment", body: "SENTINEL_ENV_BODY" },
  { title: "plan fingerprint and expiry", body: "SENTINEL_FINGERPRINT_BODY" },
] as const;

const PLAN = {
  plan_hash: "abc123def4567890",
  schema_fp: "sfp_1",
  goal: "Add a note",
  status: "pending",
  max_risk: "R2",
  environment: "staging",
  expires_at: "2099-01-01T00:00:00+00:00",
  requester_id: "usr_tunde",
  approvals: [],
  risk: { max: "R2", per_op: ["R2"], policy: { allow: true, approvers: 1, deny: false } },
  changes: [{ type: "MUST_NOT_JOIN" }],
  sections: SECTIONS,
};

type Route = (url: string, init?: RequestInit) => { status: number; body: unknown } | undefined;

function stubFetch(route: Route) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const hit = route(url, init) ?? { status: 404, body: {} };
    return {
      ok: hit.status >= 200 && hit.status < 300,
      status: hit.status,
      json: async () => hit.body,
    } as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function inboxRoute(plans: unknown[], me: string | null = "usr_amaka", decide?: Route): Route {
  return (url, init) => {
    if (url.startsWith("/api/accounts/me")) {
      return me ? { status: 200, body: { user: { id: me } } } : { status: 401, body: {} };
    }
    if (url.startsWith("/api/inbox/plans?")) return { status: 200, body: { plans } };
    if (url.includes("/decide") && decide) return decide(url, init);
    return undefined;
  };
}

async function openInbox(connection = "conn-1") {
  fireEvent.change(screen.getByLabelText("Connection"), { target: { value: connection } });
  fireEvent.submit(screen.getByRole("button", { name: "Open inbox" }).closest("form")!);
  await waitFor(() => expect(screen.getByTestId("plan-card")).toBeInTheDocument());
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  searchParams = new URLSearchParams();
});

describe("approvals inbox page (UI-S-50)", () => {
  it("renders the nine plan-card sections from the API payload, in order", async () => {
    const fetchMock = stubFetch(inboxRoute([PLAN]));
    render(<ApprovalsPage />);
    await openInbox();

    const sections = screen.getAllByTestId("plan-card-section");
    expect(sections).toHaveLength(9);
    sections.forEach((node, index) => {
      expect(within(node).getByRole("heading", { level: 3 })).toHaveTextContent(SECTIONS[index].title);
      expect(within(node).getByText(SECTIONS[index].body)).toBeInTheDocument();
    });
    expect(screen.queryByText("MUST_NOT_JOIN")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/inbox/plans?connection_id=conn-1")).toBe(true);
  });

  it("states that approve is a signature, not an apply, and shows exactly one teal primary", async () => {
    stubFetch(inboxRoute([PLAN]));
    const { container } = render(<ApprovalsPage />);
    await openInbox();
    expect(screen.getByTestId("plan-inbox-lead")).toHaveTextContent("Odoo changes only when the executor applies it");
    expect(screen.getByTestId("plan-card-signoff-note")).toHaveTextContent("Nothing is written to Odoo from this page");
    expect(screen.queryByTestId("plan-card-caution")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("plan-card-approve")).toBeEnabled());
    const primaries = container.querySelectorAll("button.bg-accent");
    expect(primaries).toHaveLength(1);
    expect(primaries[0]).toHaveTextContent("Approve this fingerprint");
    expect(screen.getByRole("button", { name: "Open inbox" }).className).not.toMatch(/bg-accent/);
  });

  it("posts the exact fingerprint after the inline confirm and reports approved, not applied", async () => {
    const decide = vi.fn<Route>(() => ({
      status: 200,
      body: { card: { ...PLAN, status: "approved", approvals: [{ user_id: "usr_amaka", approver_id: "usr_amaka", decision: "approve" }] } },
    }));
    const fetchMock = stubFetch(inboxRoute([PLAN], "usr_amaka", decide));
    render(<ApprovalsPage />);
    await openInbox();
    await waitFor(() => expect(screen.getByTestId("plan-card-approve")).toBeEnabled());

    fireEvent.click(screen.getByTestId("plan-card-approve"));
    expect(screen.getByTestId("plan-card-confirm")).toHaveTextContent("Approve abc123def456 for staging?");
    expect(decide).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("plan-card-confirm-cta"));

    await waitFor(() => expect(screen.getByTestId("plan-card-result")).toHaveTextContent(/Approved\. Not applied yet\./));
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes("/decide"))!;
    expect(call[0]).toBe("/api/inbox/plans/abc123def4567890/decide");
    expect(JSON.parse(String((call[1] as RequestInit).body))).toEqual({
      connection_id: "conn-1",
      approver_id: "usr_amaka",
      user_id: "usr_amaka",
      decision: "approve",
      plan_hash: "abc123def4567890",
      schema_fp: "sfp_1",
    });
    expect(screen.getByTestId("plan-card-status")).toHaveTextContent("Approved, not applied");
    expect(screen.queryByTestId("plan-card-approve")).not.toBeInTheDocument();
  });

  it("voids the approval when the fingerprint is stale (409)", async () => {
    stubFetch(inboxRoute([PLAN], "usr_amaka", () => ({ status: 409, body: { detail: { error: "plan_stale" } } })));
    render(<ApprovalsPage />);
    await openInbox();
    await waitFor(() => expect(screen.getByTestId("plan-card-approve")).toBeEnabled());
    fireEvent.click(screen.getByTestId("plan-card-approve"));
    fireEvent.click(screen.getByTestId("plan-card-confirm-cta"));
    await waitFor(() =>
      expect(screen.getByTestId("plan-card-status")).toHaveTextContent("Approval voided, fingerprint changed"),
    );
    expect(screen.getByTestId("plan-card-status-guide-title")).toHaveTextContent(/fingerprint changed/);
    expect(screen.queryByTestId("plan-card-approve")).not.toBeInTheDocument();
  });

  it("shows not found (never forbidden) for a plan id in the URL that is not on this connection", async () => {
    searchParams = new URLSearchParams({ connection_id: "conn-1", plan: "deadbeef00112233" });
    stubFetch(inboxRoute([PLAN]));
    render(<ApprovalsPage />);
    await waitFor(() => expect(screen.getByTestId("plan-inbox-not-found")).toBeInTheDocument());
    expect(screen.getByTestId("plan-inbox-not-found-title")).toHaveTextContent("Plan not found");
    expect(document.body.textContent).not.toMatch(/forbidden/i);
  });

  it("disables approve when signed out and explains why", async () => {
    stubFetch(inboxRoute([PLAN], null));
    render(<ApprovalsPage />);
    await openInbox();
    expect(screen.getByTestId("plan-card-approve")).toBeDisabled();
    expect(screen.getByTestId("plan-card-gate-title")).toHaveTextContent("Sign in to approve");
  });

  it("renders empty and error states with what, why, next", async () => {
    stubFetch(inboxRoute([]));
    render(<ApprovalsPage />);
    fireEvent.change(screen.getByLabelText("Connection"), { target: { value: "conn-9" } });
    fireEvent.submit(screen.getByRole("button", { name: "Open inbox" }).closest("form")!);
    await waitFor(() => expect(screen.getByTestId("plan-inbox-empty")).toBeInTheDocument());
    expect(screen.getByTestId("plan-inbox-empty-why")).toHaveTextContent("conn-9");
    cleanup();

    stubFetch((url) => (url.startsWith("/api/inbox") ? { status: 500, body: {} } : undefined));
    render(<ApprovalsPage />);
    fireEvent.change(screen.getByLabelText("Connection"), { target: { value: "conn-9" } });
    fireEvent.submit(screen.getByRole("button", { name: "Open inbox" }).closest("form")!);
    await waitFor(() => expect(screen.getByTestId("plan-inbox-error")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent("The inbox could not be loaded");
  });
});

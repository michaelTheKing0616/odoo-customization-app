import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { AppDesignPanel, BuildCustomCodeButton, removeModel } from "@/components/studio/AppDesignPanel";
import { ClarifyInterstitial } from "@/components/studio/ClarifyInterstitial";
import type { StudioAppDesign } from "@/lib/studio-session";
import fixture from "./__fixtures__/customer-health-design.json";

afterEach(() => cleanup());

const online = fixture as unknown as StudioAppDesign;
const selfHosted: StudioAppDesign = {
  ...online,
  python_needed: (online.python_needed || []).map((p) => ({ ...p, online_blocked: false, lane_note: "" })),
};

describe("AppDesignPanel", () => {
  it("renders the 9-model design with relations, extension, groups and the AI source label", () => {
    render(<AppDesignPanel design={online} />);
    expect(screen.getAllByTestId("studio-app-design-model")).toHaveLength(9);
    expect(screen.getByTestId("studio-app-design-source").textContent).toBe("Designed by AI");
    expect(screen.getByTestId("studio-app-design-relations").textContent).toMatch(/one2many/);
    expect(screen.getByText(/Contacts gets/).textContent).toMatch(/Health/);
    expect(screen.getAllByText("Config").length).toBeGreaterThan(0);
  });

  it("shows Helpdesk as an optional, deferred integration with its install note", () => {
    render(<AppDesignPanel design={online} />);
    const helpdesk = screen
      .getAllByTestId("studio-app-design-integration")
      .find((li) => li.textContent?.includes("Helpdesk"))!;
    expect(helpdesk.textContent).toMatch(/Not installed/);
    expect(helpdesk.textContent).toMatch(/Install Helpdesk, then refine/);
  });

  it("shows source-anchored delivery checks and review findings", () => {
    const design: StudioAppDesign = {
      ...online,
      intent_contract: [
        {
          id: "requirement_health_score",
          kind: "python",
          subject: "Health score recompute",
          decision: "option_a",
          evidence: { quote: "Recompute the score nightly" },
        },
      ],
      critic_findings: [
        {
          id: "finding_owner",
          kind: "ambiguity",
          subject: "Risk owner",
          detail: "The assignment rule needs your choice.",
          evidence: { quote: "assign risks to the right person" },
        },
      ],
    };
    render(<AppDesignPanel design={design} />);
    expect(screen.getByTestId("studio-intent-contract").textContent).toMatch(/Custom code module/);
    expect(screen.getByTestId("studio-intent-contract").textContent).toMatch(/Recompute the score nightly/);
    expect(screen.getByTestId("studio-intent-review").textContent).toMatch(/Risk owner/);
  });

  it("edits produce an updated design (rename, remove model and field, turn integration off)", () => {
    let current = online;
    const onChange = vi.fn((next: StudioAppDesign) => {
      current = next;
    });
    const { rerender } = render(<AppDesignPanel design={current} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("App name"), { target: { value: "Health Hub" } });
    expect(current.app_name).toBe("Health Hub");
    rerender(<AppDesignPanel design={current} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Name for x_customer_risk"), { target: { value: "Account Risk" } });
    expect(current.new_models.find((m) => m.name === "x_customer_risk")?.label).toBe("Account Risk");
    rerender(<AppDesignPanel design={current} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText(/^Remove Expansion Recommendation$/));
    expect(current.new_models).toHaveLength(8);
    rerender(<AppDesignPanel design={current} onChange={onChange} />);
    const firstFieldX = screen.getAllByLabelText(/^Remove field .* from Account Risk$/)[0];
    const before = current.new_models.find((m) => m.name === "x_customer_risk")!.fields.length;
    fireEvent.click(firstFieldX);
    expect(current.new_models.find((m) => m.name === "x_customer_risk")!.fields.length).toBe(before - 1);
    rerender(<AppDesignPanel design={current} onChange={onChange} />);
    const helpdesk = screen
      .getAllByTestId("studio-app-design-integration")
      .find((li) => li.textContent?.includes("Helpdesk"))!;
    fireEvent.click(within(helpdesk).getByText("Leave out"));
    expect(current.integrations_off).toEqual(["helpdesk"]);
  });

  it("removing a model drops links that point at it", () => {
    const next = removeModel(online, "x_success_plan");
    const links = next.new_models.flatMap((m) => m.fields).filter((f) => f.relation === "x_success_plan");
    expect(links).toHaveLength(0);
  });

  it("sends the edited design with Generate", () => {
    const onAnswer = vi.fn();
    render(
      <ClarifyInterstitial
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "We'll build: Customer Health",
          understanding: { title: "Customer Health", constraints: [] },
          app_design: online,
        }}
        onAnswer={onAnswer}
      />,
    );
    fireEvent.change(screen.getByLabelText("App name"), { target: { value: "Health Hub" } });
    fireEvent.click(screen.getByTestId("studio-diagnosis-confirm"));
    const payload = onAnswer.mock.calls[0][3];
    expect(payload.app_design.app_name).toBe("Health Hub");
    expect(payload.app_design.new_models).toHaveLength(9);
  });

  it("hides Build custom code on Online and shows the honest note instead", () => {
    const onBuild = vi.fn();
    render(<BuildCustomCodeButton design={online} onBuild={onBuild} />);
    expect(screen.queryByTestId("studio-build-custom-code")).toBeNull();
    expect(screen.getByTestId("studio-custom-code-online-note")).toBeTruthy();
    cleanup();
    render(<BuildCustomCodeButton design={selfHosted} onBuild={onBuild} />);
    fireEvent.click(screen.getByTestId("studio-build-custom-code"));
    expect(onBuild).toHaveBeenCalledTimes(1);
  });
});

describe("Install on Odoo Online", () => {
  afterEach(cleanup);
  it("opens Odoo's Apps screen in a new tab when the address is *.odoo.com (hosting unset)", () => {
    const d = fixture as unknown as StudioAppDesign;
    render(<AppDesignPanel design={d} connectionId="c1" odooUrl="https://aonb.odoo.com/odoo" onChange={() => undefined} />);
    const links = screen.getAllByRole("link", { name: /Install .* in Odoo/ });
    expect(links.length).toBeGreaterThan(0);
    for (const a of links) {
      expect(a.getAttribute("href")).toBe("https://aonb.odoo.com/odoo/apps");
      expect(a.getAttribute("target")).toBe("_blank");
    }
    expect(screen.queryByRole("button", { name: /^Install / })).toBeNull();
  });
});

describe("brief checklist", () => {
  it("puts a left-out item back and unticks a choice", async () => {
    const { putBackLeftOut, toggleChoice } = await import("./AppDesignPanel");
    const d = {
      app_name: "Bakery",
      new_models: [],
      left_out: [{ id: "a", item: "Payroll", quote: "payroll is another story" }],
      checklist_choices: [{ id: "b", item: "Website", quote: "maybe a website", ticked: true }],
    } as never;
    expect(putBackLeftOut(d, "a").left_out?.[0].put_back).toBe(true);
    expect(toggleChoice(d, "b").checklist_choices?.[0].ticked).toBe(false);
  });
});

describe("stock checks and routes", () => {
  it("shows stock use and declined services in plain words", () => {
    const design = {
      ...(fixture as unknown as StudioAppDesign),
      stock_checks: [{ item: "Quotes", label: "Using Odoo's Sales", choice: "stock" as const }],
      integration_routes: [{ service: "GIG", route: "decline" as const, label: "GIG: not connected. This needs a connector." }],
    };
    render(<AppDesignPanel design={design} />);
    expect(screen.getByText("Using Odoo's Sales")).toBeTruthy();
    expect(screen.getByText("Not connected")).toBeTruthy();
  });
});

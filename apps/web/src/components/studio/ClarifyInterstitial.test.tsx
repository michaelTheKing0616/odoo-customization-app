import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { ClarifyInterstitial, relevantCraftKeys } from "@/components/studio/ClarifyInterstitial";

afterEach(() => cleanup());

describe("ClarifyInterstitial diagnosis", () => {
  it("lets the operator edit host and lock that diagnosis", () => {
    const onAnswer = vi.fn();
    render(
      <ClarifyInterstitial
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "We'll build: Sales markup",
          help: "Custom code on the built-in Sales form.",
          host_choices: [
            { id: "sale.order", label: "Sales" },
            { id: "purchase.order", label: "Purchase" },
          ],
          understanding: {
            title: "Sales markup",
            host_model: "sale.order",
            host_label: "Sales",
            inherit_existing: true,
            needs_module: true,
            constraints: ["Withholding tax on the markup amount only"],
            out_of_scope: ["new home-screen app"],
          },
        }}
        onAnswer={onAnswer}
      />,
    );
    const card = screen.getByTestId("studio-diagnosis");
    expect(card.textContent).toMatch(/edit anything that looks wrong/i);
    fireEvent.change(screen.getByLabelText("Diagnosis title"), {
      target: { value: "PO markup" },
    });
    fireEvent.change(screen.getByLabelText("Stock form"), {
      target: { value: "purchase.order" },
    });
    fireEvent.click(screen.getByTestId("studio-diagnosis-confirm"));
    expect(onAnswer).toHaveBeenCalled();
    const payload = onAnswer.mock.calls[0][3] as { title?: string; host_model?: string };
    expect(payload.title).toBe("PO markup");
    expect(payload.host_model).toBe("purchase.order");
    expect(screen.queryByTestId("studio-clarify")).toBeNull();
  });

  it("full_app residual seeds New app tile + Built here, no custom code", () => {
    const onAnswer = vi.fn();
    render(
      <ClarifyInterstitial
        busy={false}
        onAnswer={onAnswer}
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "Does this match?",
          help: "Visitor Log residual.",
          options: [],
          understanding: {
            title: "Visitor Log",
            host_model: null,
            inherit_existing: false,
            needs_module: false,
            constraints: ["New model x_visitor_log"],
          },
        }}
      />,
    );
    expect(screen.getByText("New app tile")).toBeTruthy();
    expect(screen.getByText("Built here, no custom code")).toBeTruthy();
    expect(screen.queryByLabelText("Stock form")).toBeNull();
  });

  it("shows Nice-to-have craft chips and omits removed ones from confirm payload", () => {
    const onAnswer = vi.fn();
    render(
      <ClarifyInterstitial
        onAnswer={onAnswer}
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "We'll build: Visitor Log",
          help: "Residual full_app.",
          craft_proposals: [
            {
              id: "craft:hr.employee:x_host_id",
              on_model: "hr.employee",
              label: "Visits",
              related_model: "x_visitor_log",
              relation_field: "x_host_id",
              default_on: true,
              chip_label: "«Visits» on Employees",
            },
            {
              id: "craft:res.partner:x_company_id",
              on_model: "res.partner",
              label: "Visits",
              related_model: "x_visitor_log",
              relation_field: "x_company_id",
              default_on: false,
              chip_label: "«Visits» on Contacts",
            },
          ],
          understanding: {
            title: "Visitor Log",
            inherit_existing: false,
            needs_module: false,
            constraints: ["New model x_visitor_log", "Host→Employee"],
          },
        }}
      />,
    );
    expect(screen.getByTestId("studio-diagnosis-nice-to-have").textContent).toMatch(/Nice to have/i);
    expect(screen.getByText("«Visits» on Employees")).toBeTruthy();
    expect(screen.queryByText("«Visits» on Contacts")).toBeNull();
    fireEvent.click(screen.getByTestId("studio-craft-remove-hr.employee"));
    fireEvent.click(screen.getByTestId("studio-diagnosis-confirm"));
    const payload = onAnswer.mock.calls[0][3] as {
      craft_smart_buttons?: { on_model?: string }[];
    };
    expect(payload.craft_smart_buttons || []).toEqual([]);
  });

  it("offers extras only when they apply to the brief", () => {
    const design = {
      app_name: "Health",
      new_models: [1, 2, 3].map((n) => ({
        name: `x_m${n}`,
        label: `M${n}`,
        fields: [
          { name: "x_customer_id", ttype: "many2one", relation: "res.partner" },
          { name: "x_revenue", ttype: "float", string: "Revenue" },
        ],
      })),
    } as unknown as Parameters<typeof relevantCraftKeys>[0];
    expect(relevantCraftKeys(design, "customer health")).toEqual(["money_slots"]);
    // Multi-company is a requirement the design builds, never an optional extra.
    expect(relevantCraftKeys(design, "multi-company purchase from vendors")).toEqual([
      "money_slots",
      "purchase_link",
    ]);
  });

  it("renders every approved_craft toggle unchecked by default", () => {
    render(
      <ClarifyInterstitial
        onAnswer={vi.fn()}
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "We'll build: Maintenance",
          help: "Residual full_app.",
          understanding: {
            title: "Maintenance",
            inherit_existing: false,
            needs_module: false,
            constraints: ["Tickets with Draft→Done"],
          },
        }}
      />,
    );
    // A thin brief with no design only offers the extras that apply to it.
    expect(screen.queryByTestId("studio-craft-toggle-company_scoping")).toBeNull();
    expect(screen.queryByTestId("studio-craft-toggle-purchase_link")).toBeNull();
    const btn = screen.getByTestId("studio-craft-toggle-depth_seeds");
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    expect(btn.textContent).toMatch(/Off/i);
  });

  it("renders approved_craft toggles default off and includes them in confirm payload", () => {
    const onAnswer = vi.fn();
    render(
      <ClarifyInterstitial
        onAnswer={onAnswer}
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "We'll build: Maintenance",
          help: "Residual full_app.",
          understanding: {
            title: "Maintenance",
            inherit_existing: false,
            needs_module: false,
            constraints: ["Tickets with Draft→Done"],
          },
        }}
      />,
    );
    const panel = screen.getByTestId("studio-diagnosis-approved-craft");
    expect(panel.textContent).toMatch(/Optional extras/i);
    const moneyBtn = screen.getByTestId("studio-craft-toggle-depth_seeds");
    expect(moneyBtn.getAttribute("aria-pressed")).toBe("false");
    expect(moneyBtn.textContent).toMatch(/Off/i);
    fireEvent.click(moneyBtn);
    expect(moneyBtn.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByTestId("studio-diagnosis-confirm"));
    const payload = onAnswer.mock.calls[0][3] as {
      approved_craft?: Record<string, boolean>;
    };
    expect(payload.approved_craft?.depth_seeds).toBe(true);
    expect(payload.approved_craft?.company_scoping).toBe(false);
    expect(payload.approved_craft?.money_slots).toBe(false);
  });
});

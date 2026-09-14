import { describe, expect, it, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { ClarifyInterstitial } from "@/components/studio/ClarifyInterstitial";

describe("ClarifyInterstitial diagnosis", () => {
  it("lets the operator edit host and lock that diagnosis", () => {
    const onAnswer = vi.fn();
    render(
      <ClarifyInterstitial
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "We'll build: Sales markup",
          help: "Option A on the stock Sales form.",
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
    expect(card.textContent).toMatch(/edit if this is wrong/i);
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
    cleanup();
  });
});

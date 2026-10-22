import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AppDesignPanel } from "@/components/studio/AppDesignPanel";
import type { StudioAppDesign } from "@/lib/studio-session";

afterEach(() => cleanup());

const policy: StudioAppDesign = {
  app_name: "Policy File",
  source: "llm",
  new_models: [
    {
      name: "x_policy_file",
      label: "Policy File",
      why: "The record your brief names.",
      fields: [
        { name: "x_name", ttype: "char", string: "Name" },
        { name: "x_party_ids", ttype: "one2many", string: "Policy Parties", relation: "x_policy_file_party" },
      ],
    },
    {
      name: "x_policy_file_party",
      label: "Policy Party",
      why: "Insured people and beneficiaries on the policy.",
      suggested: true,
      fields: [
        { name: "x_policy_file_id", ttype: "many2one", string: "Policy File", relation: "x_policy_file" },
        { name: "x_partner_id", ttype: "many2one", string: "Contact", relation: "res.partner" },
      ],
    },
  ],
};

describe("AppDesignPanel suggested models", () => {
  it("marks AI-suggested models with a quiet badge and plain copy", () => {
    render(<AppDesignPanel design={policy} />);
    const badges = screen.getAllByTestId("studio-app-design-suggested");
    expect(badges).toHaveLength(1);
    expect(badges[0].textContent).toBe("Suggested");
    expect(screen.getByText("Suggested by AI, remove if you don't need it.")).toBeTruthy();
    expect(screen.getByText(/Insured people/)).toBeTruthy();
  });

  it("removes a suggested model and its link from the main record", () => {
    let current = policy;
    const onChange = vi.fn((next: StudioAppDesign) => {
      current = next;
    });
    render(<AppDesignPanel design={current} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("Remove Policy Party"));
    expect(current.new_models.map((m) => m.name)).toEqual(["x_policy_file"]);
    expect(current.new_models[0].fields.some((f) => f.relation === "x_policy_file_party")).toBe(false);
  });
});

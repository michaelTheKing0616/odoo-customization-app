/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApprovalRulesList } from "./ApprovalRulesList";
import { ApprovalsStateGuide } from "./ApprovalsStateGuide";
import { ApprovalRuleComposer } from "./ApprovalRuleComposer";
import { PRIMARY_CTA, rulesEmptyGuide } from "@/lib/approvalScreen";
import type { ApprovalRule } from "@/lib/api";

afterEach(() => cleanup());

const rule: ApprovalRule = {
  id: "rule-1",
  connection_id: "c1",
  engine: "community",
  name: "Confirm partner",
  target_model: "res.partner",
  button_method: "action_confirm",
  button_label: "Confirm",
  steps: [{ order: 1, approver_user_ids: [2] }],
  active: true,
  deployed: true,
};

describe("ApprovalsStateGuide", () => {
  it("renders what/why/next without em dashes", () => {
    const guide = rulesEmptyGuide(false, "");
    render(<ApprovalsStateGuide guide={guide} testId="g" />);
    expect(screen.getByTestId("g-title").textContent).toMatch(/No Odoo approval rules/);
    expect(screen.getByTestId("g-why").textContent).not.toMatch(/\u2014/);
    expect(screen.getByTestId("g-next").textContent?.toLowerCase()).toContain("deploy");
  });
});

describe("ApprovalRulesList", () => {
  it("shows empty guide with Deploy a rule primary", () => {
    render(
      <div className="approvals-operate">
        <ApprovalRulesList
          rules={[]}
          query=""
          testRecordId="1"
          onQueryChange={() => undefined}
          onTestRecordIdChange={() => undefined}
          onSimulate={() => undefined}
          onOpenComposer={() => undefined}
        />
      </div>,
    );
    expect(screen.getByTestId("approval-rules-empty-deploy")).toHaveTextContent("Open new rule form");
  });

  it("lists rules and simulates a click", () => {
    const onSimulate = vi.fn();
    render(
      <div className="approvals-operate">
        <ApprovalRulesList
          rules={[rule]}
          query=""
          testRecordId="1"
          onQueryChange={() => undefined}
          onTestRecordIdChange={() => undefined}
          onSimulate={onSimulate}
          onOpenComposer={() => undefined}
        />
      </div>,
    );
    expect(screen.getByText("Confirm partner")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("approval-rule-simulate-rule-1"));
    expect(onSimulate).toHaveBeenCalledWith("rule-1");
  });
});

describe("ApprovalRuleComposer", () => {
  it("keeps Deploy a rule disabled until a button is chosen", () => {
    render(
      <div className="approvals-operate">
        <ApprovalRuleComposer
          form={{
            model: "res.partner",
            name: "Button approval",
            buttonMethod: "",
            approverUserId: "2",
            testRecordId: "1",
          }}
          buttons={[]}
          onChange={() => undefined}
          onDiscover={() => undefined}
          onDeploy={(e) => e.preventDefault()}
        />
      </div>,
    );
    expect(screen.getByTestId("approval-deploy-rule")).toBeDisabled();
    expect(screen.getByTestId("approval-deploy-rule")).toHaveTextContent(PRIMARY_CTA);
  });
});

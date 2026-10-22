/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { StudioIntegrationPlanNote } from "./StudioIntegrationPlanNote";
import { deferredIntegrationsOf, integrationPlanFromSession } from "@/lib/integration-plan";

const RESPONSE = {
  id: "s1",
  status: "ready",
  integration_plan: {
    primary_module: null,
    edition: "community",
    hosting: "online",
    core_built: true,
    integrations: [
      { module: "crm", app_label: "CRM", model: "crm.lead", status: "available", note: "" },
      {
        module: "project",
        app_label: "Project",
        model: "project.task",
        status: "deferred",
        note: "Project is not installed, so its links are left out for now. Install Project, then refine this app to add them.",
      },
      {
        module: "helpdesk",
        app_label: "Helpdesk",
        model: "helpdesk.ticket",
        status: "left_out",
        note: "Helpdesk was left out: it is an Odoo Enterprise app and this database is Community. To add it later, move to Odoo Enterprise, install Helpdesk, then refine this app.",
      },
    ],
    python_pieces: [
      { key: "computed_score", label: "Computed scores (weighted 0-100 score)", online_blocked: "true" },
      { key: "rules_engine", label: "Rules engine", online_blocked: "true" },
    ],
  },
};

afterEach(cleanup);

describe("StudioIntegrationPlanNote", () => {
  it("renders available, deferred, left out and Option A rows from a response", () => {
    render(<StudioIntegrationPlanNote plan={integrationPlanFromSession(RESPONSE)} />);
    const root = screen.getByTestId("studio-integration-plan");
    expect(root.getAttribute("data-tone")).toBe("amber");
    expect(screen.getByTestId("studio-plan-available").textContent).toContain("Uses CRM.");
    expect(screen.getByTestId("studio-plan-project").textContent).toContain("Install Project, then refine");
    expect(screen.getByTestId("studio-plan-helpdesk").textContent).toContain("Enterprise");
    const optionA = screen.getByTestId("studio-plan-option-a").textContent || "";
    expect(optionA).toContain("Odoo.sh");
    expect(optionA).toContain("cannot install on Odoo Online");
    expect(root.textContent || "").not.toMatch(/\u2014/);
  });

  it("reads the persisted turn when the response field is gone", () => {
    const plan = integrationPlanFromSession({
      conversation: [
        { role: "assistant", kind: "integration_plan", content: "x", metadata: RESPONSE },
        {
          role: "assistant",
          kind: "integration_plan",
          content: "x",
          metadata: { integration_plan: RESPONSE.integration_plan },
        },
      ],
    });
    expect(plan?.integrations).toHaveLength(3);
    expect(deferredIntegrationsOf(plan).map((d) => d.status)).toEqual(["deferred", "left_out"]);
  });

  it("renders nothing without a plan, and stays quiet when everything is linked", () => {
    const { container } = render(<StudioIntegrationPlanNote plan={null} />);
    expect(container.textContent).toBe("");
    render(
      <StudioIntegrationPlanNote
        plan={{
          integrations: [{ module: "crm", app_label: "CRM", model: "crm.lead", status: "available", note: "" }],
        }}
      />,
    );
    expect(screen.getByTestId("studio-integration-plan").getAttribute("data-tone")).toBe("quiet");
  });
});

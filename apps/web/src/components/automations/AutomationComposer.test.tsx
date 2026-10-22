/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AutomationComposer } from "./AutomationComposer";
import { defaultComposerForm, LIBRARY_FINE_SNIPPET } from "@/lib/automationForm";
import type { Connection } from "@/lib/api";

afterEach(() => cleanup());

const connection: Connection = {
  id: "c1",
  name: "Test",
  url: "http://127.0.0.1:8069",
  db_name: "odoo_dev",
  username: "admin",
  server_version: "19.0",
  write_mode: "standard",
  created_at: null,
  updated_at: null,
  capabilities: {
    major: 19,
    edition: "community",
    server_version: "19.0",
    ga: true,
    message: "ok",
    hosting_hint: "self_hosted",
    supported: [
      "object_write_update_path",
      "related_write_dotted_path",
      "object_create_crud_model",
      "base_automation_safe_triggers",
    ],
    unsupported: [],
  },
};

describe("AutomationComposer", () => {
  it("applies a conversational prompt into the form", () => {
    const onChange = vi.fn();
    render(
      <div className="automations-operate">
        <AutomationComposer
          connectionId="c1"
          connection={connection}
          form={defaultComposerForm()}
          onChange={onChange}
          onSubmit={(e) => e.preventDefault()}
          busy={false}
          canSubmit
          supportedTriggers={null}
          activityTypes={[]}
          mailTemplates={[]}
          models={[]}
        />
      </div>,
    );
    fireEvent.change(screen.getByTestId("automations-prompt-input"), {
      target: { value: "On create of x_visitor_log, set status" },
    });
    fireEvent.click(screen.getByTestId("automations-prompt-apply"));
    expect(onChange).toHaveBeenCalled();
    const patch = onChange.mock.calls.at(-1)?.[0] ?? {};
    expect(patch.model).toBe("x_visitor_log");
    expect(patch.trigger).toBe("on_create");
  });

  it("shows Option A path for python_module and never offers live code CTA", () => {
    render(
      <div className="automations-operate">
        <AutomationComposer
          connectionId="c1"
          connection={connection}
          form={{
            ...defaultComposerForm("x_lib_loan"),
            action_kind: "python_module",
            python_code: LIBRARY_FINE_SNIPPET,
            module_technical_name: "library_fine_on_return",
          }}
          onChange={vi.fn()}
          onSubmit={(e) => e.preventDefault()}
          busy={false}
          canSubmit
          supportedTriggers={null}
          activityTypes={[]}
          mailTemplates={[]}
          models={[]}
        />
      </div>,
    );
    expect(screen.getByTestId("automations-option-a-title")).toHaveTextContent("Custom code");
    expect(screen.getByTestId("automations-option-a-steps").querySelectorAll("li")).toHaveLength(3);
    expect(screen.getByTestId("automations-submit")).toHaveTextContent("Generate module zip");
    expect(screen.queryByText(/Run Python live/i)).not.toBeInTheDocument();
  });

  it("shows webhook advanced confirmation guide", () => {
    render(
      <div className="automations-operate">
        <AutomationComposer
          connectionId="c1"
          connection={connection}
          form={{
            ...defaultComposerForm("x_visitor_log"),
            action_kind: "webhook",
            webhook_url: "https://example.com/hooks/odoo",
          }}
          onChange={vi.fn()}
          onSubmit={(e) => e.preventDefault()}
          busy={false}
          canSubmit
          supportedTriggers={null}
          activityTypes={[]}
          mailTemplates={[]}
          models={[]}
        />
      </div>,
    );
    expect(screen.getByTestId("automations-webhook-confirm-title")).toHaveTextContent(
      "Webhook needs advanced confirmation",
    );
  });
});

"use client";

import { useState } from "react";
import { GatingCallout } from "@/components/GatingCallout";
import type { AutomationsGateResponse, GatingChoiceId } from "@/lib/api";

const GATED: AutomationsGateResponse = {
  automations: {
    feature: "automations",
    title: "Automations aren't available on this connection",
    why: "Automation rules need the base_automation module, which isn't installed on this Odoo Online instance (it ships with Odoo's Custom plan).",
    options: [
      "Upgrade the Odoo subscription to the Custom plan to unlock live automations.",
      "Deploying to Odoo.sh or self-hosted? Export this as a module with scheduled actions instead.",
      "Or leave automations out — everything else here works fully.",
    ],
    available: false,
    capability_key: "base_automation",
    gating_choices: [
      { id: "upgrade_plan", label: "Upgrade the Odoo subscription to the Custom plan" },
      { id: "export_module", label: "Export as a module with scheduled actions instead" },
      { id: "leave_out", label: "Leave automations out" },
    ],
  },
  approvals: {
    feature: "approval_rules",
    title: "Approval rules aren't available on this connection",
    why: "Approval rules are Enterprise-only and were not detected on this database.",
    options: [],
    available: false,
    capability_key: "approval_rules_studio",
    gating_choices: [],
  },
};

export default function E2EAutomationGatingHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [choice, setChoice] = useState<GatingChoiceId | null>(null);

  if (!enabled) {
    return <p>E2E harness disabled</p>;
  }

  return (
    <main className="p-8">
      <h1 className="mb-4 text-lg font-semibold">Automation gating e2e harness</h1>
      <GatingCallout
        gating={GATED.automations}
        selectedChoice={choice}
        onSelectChoice={setChoice}
      />
      <p className="mt-4 text-sm" data-testid="gating-selected">
        {choice ?? "none"}
      </p>
    </main>
  );
}

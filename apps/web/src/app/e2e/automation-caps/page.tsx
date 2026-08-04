"use client";

import { useMemo, useState } from "react";
import { AutomationActionKindSelect } from "@/components/AutomationActionKindSelect";
import type { AutomationActionKind, CapabilityMatrix, Connection } from "@/lib/api";
import {
  advancedMutationAllowed,
  belowMinMajor,
  currencyFieldSupported,
  defaultWindowViewMode,
  mutationAllowed,
  scaffoldApplyAllowed,
} from "@/lib/capabilities";

const ODOO_16_CAPS: CapabilityMatrix = {
  major: 16,
  edition: "community",
  server_version: "16.0",
  ga: false,
  message: "Odoo 16 Community — experimental",
  supported: [
    "base_automation_safe_triggers",
    "list_tree_fallback",
    "object_create_crud_model",
    "smart_button_inherit_box",
    "view_inject_inherit",
    "view_inject_mutate",
  ],
  unsupported: [
    {
      id: "related_write_dotted_path",
      label: "Related write (dotted update_path)",
      reason: "Not available on Odoo 16 (community)",
    },
    {
      id: "object_write_update_path",
      label: "Update field (object_write)",
      reason: "Not available on Odoo 16 (community)",
    },
    {
      id: "list_as_list_type",
      label: "List as list type",
      reason: "Not available on Odoo 16 (community)",
    },
  ],
};

const ODOO_19_CAPS: CapabilityMatrix = {
  major: 19,
  edition: "community",
  server_version: "19.0",
  ga: true,
  message: "Odoo 19 Community — GA",
  supported: [
    "base_automation_safe_triggers",
    "list_as_list_type",
    "list_tree_fallback",
    "object_create_crud_model",
    "object_write_update_path",
    "related_write_dotted_path",
    "smart_button_inherit_box",
    "view_inject_inherit",
    "view_inject_mutate",
  ],
  unsupported: [],
};

function mockConnection(
  id: string,
  caps: CapabilityMatrix | null,
): Connection {
  return {
    id,
    name: caps ? `E2E Mock Odoo ${caps.major}` : "E2E Unprobed",
    url: "http://127.0.0.1:8072",
    db_name: "odoo_dev",
    username: "admin",
    server_version: caps?.server_version ?? null,
    write_mode: "standard",
    created_at: null,
    updated_at: null,
    capabilities: caps,
  };
}

type HarnessProfile = "odoo16" | "odoo19" | "unprobed";

export default function E2EAutomationCapsHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [actionKind, setActionKind] = useState<AutomationActionKind>("create_activity");
  const [profile, setProfile] = useState<HarnessProfile>("odoo16");

  const connection = useMemo(() => {
    if (profile === "unprobed") return mockConnection("e2e-unprobed", null);
    if (profile === "odoo19") return mockConnection("e2e-mock-19", ODOO_19_CAPS);
    return mockConnection("e2e-mock-16", ODOO_16_CAPS);
  }, [profile]);

  if (!enabled) {
    return <p>E2E harness disabled</p>;
  }

  const canMutate = mutationAllowed(connection);
  const canAdvanced = advancedMutationAllowed(connection);
  const canScaffold = scaffoldApplyAllowed(connection);
  const canScaffoldWrite = scaffoldApplyAllowed(connection, {
    requireObjectWrite: true,
  });
  const blockedByMin19 = belowMinMajor(connection, 19);
  const currencyOk = currencyFieldSupported(connection);
  const viewMode = defaultWindowViewMode(connection);

  return (
    <main className="p-8">
      <h1 className="mb-4 text-lg font-semibold">Automation / mutation caps e2e harness</h1>

      <label className="mb-4 block text-sm">
        Profile{" "}
        <select
          data-testid="harness-profile"
          className="border px-2 py-1"
          value={profile}
          onChange={(e) => setProfile(e.target.value as HarnessProfile)}
        >
          <option value="odoo16">Odoo 16 experimental</option>
          <option value="odoo19">Odoo 19 GA</option>
          <option value="unprobed">Unprobed (no capabilities)</option>
        </select>
      </label>

      <p className="mb-4 text-sm text-neutral-600" data-testid="harness-major">
        Mock connection major: {connection.capabilities?.major ?? "unknown"}
      </p>

      <AutomationActionKindSelect
        connection={connection}
        value={actionKind}
        onChange={setActionKind}
        className="border px-3 py-2"
      />
      <p className="mt-4 text-sm" data-testid="selected-action-kind">
        {actionKind}
      </p>

      <section className="mt-8 space-y-2 text-sm" data-testid="mutation-gates">
        <p data-testid="gate-mutation-allowed">{canMutate ? "yes" : "no"}</p>
        <p data-testid="gate-advanced-mutation-allowed">{canAdvanced ? "yes" : "no"}</p>
        <p data-testid="gate-scaffold-apply-allowed">{canScaffold ? "yes" : "no"}</p>
        <p data-testid="gate-scaffold-object-write">{canScaffoldWrite ? "yes" : "no"}</p>
        <p data-testid="gate-below-min-major-19">{blockedByMin19 ? "yes" : "no"}</p>
        <p data-testid="gate-currency-field">{currencyOk ? "yes" : "no"}</p>
        <p data-testid="gate-default-view-mode">{viewMode}</p>
        <button
          type="button"
          data-testid="mutate-primary"
          disabled={!canMutate}
          className="border px-3 py-1 disabled:opacity-40"
        >
          Primary mutate
        </button>
        <button
          type="button"
          data-testid="mutate-advanced"
          disabled={!canAdvanced}
          className="ml-2 border px-3 py-1 disabled:opacity-40"
        >
          Advanced mutate
        </button>
      </section>
    </main>
  );
}

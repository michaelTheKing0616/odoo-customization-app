"use client";

import type { AutomationActionKind, Connection } from "@/lib/api";
import { connectionSupports } from "@/lib/capabilities";

type Props = {
  connection: Connection | null | undefined;
  value: AutomationActionKind;
  onChange: (kind: AutomationActionKind) => void;
  className?: string;
  "data-testid"?: string;
};

/** Automations “Do” action kind select — gates update_path caps fail-closed. */
export function AutomationActionKindSelect({
  connection,
  value,
  onChange,
  className,
  "data-testid": testId = "automation-action-kind",
}: Props) {
  return (
    <select
      data-testid={testId}
      value={value}
      onChange={(e) => onChange(e.target.value as AutomationActionKind)}
      className={className}
    >
      <option
        value="update_field"
        disabled={!connectionSupports(connection, "object_write_update_path")}
      >
        Update field (safe)
      </option>
      <option
        value="related_write"
        disabled={!connectionSupports(connection, "related_write_dotted_path")}
      >
        Related write — update linked record (safe)
        {!connectionSupports(connection, "related_write_dotted_path")
          ? " — unavailable on this Odoo"
          : ""}
      </option>
      <option value="create_activity">Create activity (safe)</option>
      <option
        value="create_record"
        disabled={!connectionSupports(connection, "object_create_crud_model")}
      >
        Create record (safe)
      </option>
      <option value="mail_post">Send / post mail (safe)</option>
      <option value="webhook">Webhook (advanced, requires confirm)</option>
      <option value="sms">Send SMS (advanced, requires confirm)</option>
      <option value="followers">Add followers (advanced, requires confirm)</option>
      <option value="remove_followers">
        Remove followers (advanced, requires confirm)
      </option>
      <option value="python_module">
        Custom Python → module zip (Option A, not live yet)
      </option>
      <option value="code_live">
        Custom Python → live now (advanced, requires confirm)
      </option>
    </select>
  );
}

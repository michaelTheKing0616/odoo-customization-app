"use client";

import type { AutomationActionKind, Connection } from "@/lib/api";
import { connectionSupports } from "@/lib/capabilities";
import { cn } from "@/lib/cn";

type Props = {
  connection: Connection | null | undefined;
  value: AutomationActionKind;
  onChange: (kind: AutomationActionKind) => void;
  className?: string;
  "data-testid"?: string;
  id?: string;
};

type KindOption = {
  value: AutomationActionKind;
  label: string;
  disabled?: boolean;
};

function safeOptions(connection: Connection | null | undefined): KindOption[] {
  return [
    {
      value: "update_field",
      label: "Update field",
      disabled: !connectionSupports(connection, "object_write_update_path"),
    },
    {
      value: "related_write",
      label: connectionSupports(connection, "related_write_dotted_path")
        ? "Update linked record"
        : "Update linked record — unavailable on this Odoo",
      disabled: !connectionSupports(connection, "related_write_dotted_path"),
    },
    { value: "create_activity", label: "Schedule activity" },
    {
      value: "create_record",
      label: "Create record",
      disabled: !connectionSupports(connection, "object_create_crud_model"),
    },
    { value: "mail_post", label: "Send or post mail" },
  ];
}

const ADVANCED_OPTIONS: KindOption[] = [
  { value: "webhook", label: "Call webhook (confirm)" },
  { value: "sms", label: "Send SMS (confirm)" },
  { value: "followers", label: "Add followers (confirm)" },
  { value: "remove_followers", label: "Remove followers (confirm)" },
  { value: "code_live", label: "Run Python live (confirm)" },
];

const OPTION_A: KindOption[] = [
  { value: "python_module", label: "Export Python module (not live)" },
];

/** Automations “Then” action kind select — gates update_path caps fail-closed. */
export function AutomationActionKindSelect({
  connection,
  value,
  onChange,
  className,
  id,
  "data-testid": testId = "automation-action-kind",
}: Props) {
  return (
    <select
      id={id}
      data-testid={testId}
      value={value}
      onChange={(e) => onChange(e.target.value as AutomationActionKind)}
      className={cn(
        "h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2",
        className,
      )}
    >
      <optgroup label="Safe">
        {safeOptions(connection).map((opt) => (
          <option key={opt.value} value={opt.value} disabled={opt.disabled}>
            {opt.label}
          </option>
        ))}
      </optgroup>
      <optgroup label="Advanced">
        {ADVANCED_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </optgroup>
      <optgroup label="Option A">
        {OPTION_A.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </optgroup>
    </select>
  );
}

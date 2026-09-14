"use client";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/layout-primitives";
import { IconAccess } from "@/components/ui/icons";
import type { ModuleSpecAccessRule } from "@/lib/modulespec-types";

type ModuleSpecSecurityPanelProps = {
  rules: ModuleSpecAccessRule[];
  readOnly?: boolean;
  onChange: (next: ModuleSpecAccessRule[]) => void;
};

function asChecked(value: number | boolean | undefined): boolean {
  return value === true || value === 1;
}

export function ModuleSpecSecurityPanel({
  rules,
  readOnly,
  onChange,
}: ModuleSpecSecurityPanelProps) {
  function patch(index: number, partial: Partial<ModuleSpecAccessRule>) {
    onChange(rules.map((row, i) => (i === index ? { ...row, ...partial } : row)));
  }

  function addRule() {
    onChange([
      ...rules,
      {
        id: `access_rule_${rules.length + 1}`,
        name: "Internal user",
        model: "model_x_new_model_1",
        group: "base.group_user",
        perm_read: 1,
        perm_write: 1,
        perm_create: 1,
        perm_unlink: 0,
      },
    ]);
  }

  return (
    <div className="space-y-3" data-testid="modulespec-security">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">Access rules</h3>
        {!readOnly ? (
          <Button type="button" variant="secondary" size="sm" onClick={addRule}>
            Add access rule
          </Button>
        ) : null}
      </div>
      {rules.length === 0 ? (
        <EmptyState
          icon={<IconAccess className="h-5 w-5" />}
          title="No access rules in this spec"
          description="Apply may add Internal User ACL. Review CRUD here before Generate UI. Record rules stay on the Access surface."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[42rem] text-left text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-1 pr-2 font-medium">Name</th>
                <th className="py-1 pr-2 font-medium">Model</th>
                <th className="py-1 pr-2 font-medium">Group</th>
                <th className="py-1 pr-2 font-medium">R</th>
                <th className="py-1 pr-2 font-medium">W</th>
                <th className="py-1 pr-2 font-medium">C</th>
                <th className="py-1 pr-2 font-medium">U</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rules.map((rule, index) => (
                <tr key={`${rule.id}-${index}`} className="border-t border-border-subtle">
                  <td className="py-2 pr-2">
                    <input
                      disabled={readOnly}
                      value={rule.name ?? ""}
                      onChange={(event) => patch(index, { name: event.target.value })}
                      className="input text-xs"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      disabled={readOnly}
                      value={rule.model ?? ""}
                      onChange={(event) => patch(index, { model: event.target.value })}
                      className="input font-mono text-xs"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      disabled={readOnly}
                      value={rule.group ?? ""}
                      onChange={(event) => patch(index, { group: event.target.value })}
                      className="input font-mono text-xs"
                    />
                  </td>
                  {(["perm_read", "perm_write", "perm_create", "perm_unlink"] as const).map((key) => (
                    <td key={key} className="py-2 pr-2">
                      <input
                        type="checkbox"
                        disabled={readOnly}
                        checked={asChecked(rule[key])}
                        onChange={(event) => patch(index, { [key]: event.target.checked ? 1 : 0 })}
                        aria-label={`${key} ${rule.name ?? ""}`}
                      />
                    </td>
                  ))}
                  <td className="py-2">
                    {!readOnly ? (
                      <button
                        type="button"
                        className="text-xs text-danger"
                        onClick={() => onChange(rules.filter((_, i) => i !== index))}
                      >
                        Remove
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

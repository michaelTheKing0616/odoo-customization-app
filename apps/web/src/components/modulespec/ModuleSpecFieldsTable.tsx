"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { fieldTypeLabel, needsRelation } from "@/lib/builderForm";
import { MODULESPEC_TTYPES, type ModuleSpecField } from "@/lib/modulespec-types";

type ModuleSpecFieldsTableProps = {
  fields: ModuleSpecField[];
  readOnly?: boolean;
  onAdd: () => void;
  onUpdate: (index: number, field: ModuleSpecField) => void;
  onRemove: (index: number) => void;
};

export function ModuleSpecFieldsTable({
  fields,
  readOnly,
  onAdd,
  onUpdate,
  onRemove,
}: ModuleSpecFieldsTableProps) {
  const [openHelp, setOpenHelp] = useState<number | null>(null);
  return (
    <div className="mt-4" data-testid="modulespec-fields">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">Fields</h3>
        {!readOnly ? (
          <Button type="button" variant="secondary" size="sm" onClick={onAdd} data-testid="modulespec-add-field">
            Add field
          </Button>
        ) : null}
      </div>
      {fields.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No fields on this model yet.</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-1 pr-2 font-medium">Name</th>
                <th className="py-1 pr-2 font-medium">Type</th>
                <th className="py-1 pr-2 font-medium">Label</th>
                <th className="py-1 pr-2 font-medium">Relation</th>
                <th className="py-1 pr-2 font-medium">Required</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {fields.map((field, index) => {
                const relationNeeded = needsRelation(String(field.ttype || "char"));
                return (
                  <tr key={`${field.name}-${index}`} className="border-t border-border-subtle align-top">
                    <td className="py-2 pr-2">
                      <input
                        disabled={readOnly}
                        value={field.name}
                        onChange={(event) => onUpdate(index, { ...field, name: event.target.value })}
                        className="input font-mono text-xs"
                      />
                    </td>
                    <td className="py-2 pr-2">
                      <select
                        disabled={readOnly}
                        value={field.ttype || "char"}
                        onChange={(event) => onUpdate(index, { ...field, ttype: event.target.value })}
                        className="input text-xs"
                      >
                        {MODULESPEC_TTYPES.map((type) => (
                          <option key={type} value={type}>
                            {fieldTypeLabel(type)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-2 pr-2">
                      <input
                        disabled={readOnly}
                        value={field.string ?? ""}
                        onChange={(event) => onUpdate(index, { ...field, string: event.target.value })}
                        className="input text-xs"
                      />
                    </td>
                    <td className="py-2 pr-2">
                      <input
                        disabled={readOnly || !relationNeeded}
                        value={field.relation ?? ""}
                        onChange={(event) =>
                          onUpdate(index, { ...field, relation: event.target.value || null })
                        }
                        placeholder={relationNeeded ? "res.partner" : "—"}
                        className="input font-mono text-xs"
                      />
                    </td>
                    <td className="py-2 pr-2">
                      <input
                        type="checkbox"
                        disabled={readOnly}
                        checked={Boolean(field.required)}
                        onChange={(event) =>
                          onUpdate(index, { ...field, required: event.target.checked })
                        }
                        aria-label={`Required ${field.name}`}
                      />
                    </td>
                    <td className="py-2 pl-2 whitespace-nowrap">
                      <button
                        type="button"
                        className="text-xs text-muted hover:text-ink"
                        onClick={() => setOpenHelp(openHelp === index ? null : index)}
                      >
                        More
                      </button>
                      {!readOnly ? (
                        <button
                          type="button"
                          className="ml-2 text-xs text-danger"
                          onClick={() => onRemove(index)}
                        >
                          Remove
                        </button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {openHelp !== null && fields[openHelp] ? (
        <div className="mt-3 grid gap-3 rounded-md border border-border-subtle bg-surface-raised p-3 md:grid-cols-2">
          <label className="text-sm">
            <span className="studio-field-label">Help</span>
            <input
              disabled={readOnly}
              value={fields[openHelp].help ?? ""}
              onChange={(event) =>
                onUpdate(openHelp, { ...fields[openHelp], help: event.target.value || null })
              }
              className="input mt-1"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              disabled={readOnly}
              checked={Boolean(fields[openHelp].readonly)}
              onChange={(event) =>
                onUpdate(openHelp, { ...fields[openHelp], readonly: event.target.checked })
              }
            />
            Read only
          </label>
          {String(fields[openHelp].ttype) === "selection" ? (
            <label className="text-sm md:col-span-2">
              <span className="studio-field-label">Selection</span>
              <input
                disabled={readOnly}
                value={fields[openHelp].selection ?? ""}
                onChange={(event) =>
                  onUpdate(openHelp, { ...fields[openHelp], selection: event.target.value || null })
                }
                className="input mt-1 font-mono text-xs"
              />
            </label>
          ) : null}
          {String(fields[openHelp].ttype) === "one2many" ? (
            <label className="text-sm md:col-span-2">
              <span className="studio-field-label">Inverse field</span>
              <input
                disabled={readOnly}
                value={fields[openHelp].relation_field ?? ""}
                onChange={(event) =>
                  onUpdate(openHelp, {
                    ...fields[openHelp],
                    relation_field: event.target.value || null,
                  })
                }
                className="input mt-1 font-mono text-xs"
              />
            </label>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

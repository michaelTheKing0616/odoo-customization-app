"use client";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/layout-primitives";
import { IconMenus } from "@/components/ui/icons";
import type { ModuleSpecMenu } from "@/lib/modulespec-types";

type ModuleSpecMenusPanelProps = {
  menus: ModuleSpecMenu[];
  readOnly?: boolean;
  onChange: (next: ModuleSpecMenu[]) => void;
};

export function ModuleSpecMenusPanel({ menus, readOnly, onChange }: ModuleSpecMenusPanelProps) {
  function patch(index: number, partial: Partial<ModuleSpecMenu>) {
    onChange(menus.map((row, i) => (i === index ? { ...row, ...partial } : row)));
  }

  function addMenu() {
    onChange([
      ...menus,
      {
        name: "New menu",
        sequence: (menus.length + 1) * 10,
        technical_name: `menu_item_${menus.length + 1}`,
      },
    ]);
  }

  return (
    <div className="space-y-3" data-testid="modulespec-menus">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">Menus</h3>
        {!readOnly ? (
          <Button type="button" variant="secondary" size="sm" onClick={addMenu}>
            Add menu
          </Button>
        ) : null}
      </div>
      {menus.length === 0 ? (
        <EmptyState
          icon={<IconMenus className="h-5 w-5" />}
          title="No menus in this spec"
          description="Generate UI can write an app root and model children. Add items here when you need to pin the tree."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-1 pr-2 font-medium">Label</th>
                <th className="py-1 pr-2 font-medium">Technical</th>
                <th className="py-1 pr-2 font-medium">Parent</th>
                <th className="py-1 pr-2 font-medium">Action</th>
                <th className="py-1 pr-2 font-medium">Seq</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {menus.map((menu, index) => (
                <tr key={`${menu.technical_name}-${index}`} className="border-t border-border-subtle">
                  <td className="py-2 pr-2">
                    <input
                      disabled={readOnly}
                      value={menu.name ?? ""}
                      onChange={(event) => patch(index, { name: event.target.value })}
                      className="input text-xs"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      disabled={readOnly}
                      value={menu.technical_name ?? menu.xml_id ?? ""}
                      onChange={(event) => patch(index, { technical_name: event.target.value })}
                      className="input font-mono text-xs"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      disabled={readOnly}
                      value={menu.parent_xml_id ?? ""}
                      onChange={(event) => patch(index, { parent_xml_id: event.target.value })}
                      className="input font-mono text-xs"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      disabled={readOnly}
                      value={menu.action_xml_id ?? ""}
                      onChange={(event) => patch(index, { action_xml_id: event.target.value })}
                      className="input font-mono text-xs"
                    />
                  </td>
                  <td className="py-2 pr-2 w-20">
                    <input
                      disabled={readOnly}
                      type="number"
                      value={menu.sequence ?? 10}
                      onChange={(event) => patch(index, { sequence: Number(event.target.value) })}
                      className="input text-xs"
                    />
                  </td>
                  <td className="py-2">
                    {!readOnly ? (
                      <button
                        type="button"
                        className="text-xs text-danger"
                        onClick={() => onChange(menus.filter((_, i) => i !== index))}
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

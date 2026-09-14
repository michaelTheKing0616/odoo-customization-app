"use client";

import { CodeEditorPanel } from "@/components/CodeEditorPanel";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";

type ModuleSpecCustomCodePanelProps = {
  blocks: Array<Record<string, unknown>>;
  readOnly?: boolean;
  canEditCustomCode?: boolean;
  lintBusy?: boolean;
  sandboxBusy?: boolean;
  onAdd: () => void;
  onUpdate: (index: number, partial: Record<string, unknown>) => void;
  onRemove: (index: number) => void;
  onLintBlocks?: () => void;
  onExportSandbox?: () => void;
};

export function ModuleSpecCustomCodePanel({
  blocks,
  readOnly,
  canEditCustomCode,
  lintBusy,
  sandboxBusy,
  onAdd,
  onUpdate,
  onRemove,
  onLintBlocks,
  onExportSandbox,
}: ModuleSpecCustomCodePanelProps) {
  return (
    <div className="space-y-4" data-testid="modulespec-custom-code">
      <Callout variant="warning" title="Code ships as a module">
        Custom Python/XML never applies via live Generate UI. Export zip, sandbox-test, then
        promote. Completeness is not this path.
      </Callout>
      {!canEditCustomCode ? (
        <p className="text-sm text-muted">
          Custom logic is preserved from import — read-only unless you have the developer role.
        </p>
      ) : null}
      {canEditCustomCode && !readOnly ? (
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="secondary" onClick={onAdd}>
            Add code block
          </Button>
          {onLintBlocks ? (
            <Button type="button" size="sm" variant="secondary" onClick={onLintBlocks} disabled={lintBusy}>
              Lint blocks
            </Button>
          ) : null}
          {onExportSandbox ? (
            <Button type="button" size="sm" onClick={onExportSandbox} disabled={sandboxBusy}>
              Export and sandbox-test
            </Button>
          ) : null}
        </div>
      ) : null}
      {blocks.length === 0 ? (
        <p className="text-sm text-muted">None — metadata-only spec.</p>
      ) : (
        <ul className="space-y-4">
          {blocks.map((block, index) => (
            <li key={index} className="border border-border-subtle bg-surface-raised p-3">
              {canEditCustomCode && !readOnly ? (
                <div className="space-y-3">
                  <label className="block text-xs text-muted">
                    Source file
                    <input
                      className="input mt-1 font-mono text-xs"
                      value={String(block.source_file || block.path || "")}
                      onChange={(event) => onUpdate(index, { source_file: event.target.value })}
                    />
                  </label>
                  <label className="block text-xs text-muted">
                    Kind
                    <select
                      className="input mt-1 text-xs"
                      value={String(block.kind || "python")}
                      onChange={(event) => onUpdate(index, { kind: event.target.value })}
                    >
                      <option value="python">python</option>
                      <option value="python_methods">python_methods</option>
                      <option value="xml">xml</option>
                    </select>
                  </label>
                  <CodeEditorPanel
                    value={String(block.content || block.source || "")}
                    onChange={(code) => onUpdate(index, { content: code })}
                    label={String(block.source_file || "block")}
                    rows={14}
                    testId={`custom-code-block-${index}`}
                  />
                  <Button type="button" size="sm" variant="ghost" onClick={() => onRemove(index)}>
                    Remove block
                  </Button>
                </div>
              ) : (
                <>
                  <p className="font-mono text-xs text-muted">
                    {String(block.kind || "opaque")} ·{" "}
                    {String(block.source_file || block.path || block.model || "")}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {String(block.reason || "custom_logic_not_editable_visually")}
                  </p>
                  <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs">
                    {typeof block.content === "string"
                      ? block.content.slice(0, 4000)
                      : typeof block.source === "string"
                        ? block.source.slice(0, 4000)
                        : JSON.stringify(block.snippets || block, null, 2).slice(0, 4000)}
                  </pre>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

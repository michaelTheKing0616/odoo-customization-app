"use client";

import { useState } from "react";
import { ReportFieldPicker } from "@/components/reports/ReportFieldPicker";
import {
  ReorderableBlocks,
  moveIndex,
} from "@/components/ui/canvas/ReorderableBlocks";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input } from "@/components/ui/Input";
import type { FieldRow } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  blocksToPreviewHtml,
  compileInheritFragment,
  compileQwebViewBlocks,
  newQwebBlockId,
  type QwebViewBlock,
} from "./qwebViewBlocks";
import { QwebPaperPreview } from "./QwebPaperPreview";
import { refuseUnsafeQwebViewSave } from "./qwebUnsafeGate";
import type { QwebViewListRow } from "./QwebViewsListPanel";
import styles from "./QwebViewsPage.module.css";

type EditorTab = "visual" | "source";
type SaveStrategy = "inherit" | "overwrite";

export type QwebViewDetail = QwebViewListRow & {
  arch?: string | null;
  blocks?: QwebViewBlock[] | null;
  blocks_parseable?: boolean;
  existing_t_call_targets?: string[];
};

type Props = {
  view: QwebViewDetail | null;
  arch: string;
  blocks: QwebViewBlock[];
  fields: FieldRow[];
  fieldsLoading?: boolean;
  editorTab: EditorTab;
  strategy: SaveStrategy;
  inheritXpath: string;
  inheritPosition: string;
  existingTCalls: string[];
  busy?: boolean;
  canMutate?: boolean;
  mutateBlocked?: string | null;
  onArchChange: (v: string) => void;
  onBlocksChange: (blocks: QwebViewBlock[]) => void;
  onEditorTabChange: (tab: EditorTab) => void;
  onStrategyChange: (s: SaveStrategy) => void;
  onInheritXpathChange: (v: string) => void;
  onInheritPositionChange: (v: string) => void;
  onSave: () => void | Promise<void>;
  onError: (msg: string) => void;
};

export function QwebViewsEditor({
  view,
  arch,
  blocks,
  fields,
  fieldsLoading,
  editorTab,
  strategy,
  inheritXpath,
  inheritPosition,
  existingTCalls,
  busy,
  canMutate = true,
  mutateBlocked,
  onArchChange,
  onBlocksChange,
  onEditorTabChange,
  onStrategyChange,
  onInheritXpathChange,
  onInheritPositionChange,
  onSave,
  onError,
}: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [insertField, setInsertField] = useState("");

  const selected = blocks.find((b) => b.id === selectedId) ?? null;
  const previewHtml =
    editorTab === "visual" ? blocksToPreviewHtml(blocks) : arch;

  function moveBlock(id: string, dir: -1 | 1) {
    const idx = blocks.findIndex((b) => b.id === id);
    if (idx < 0) return;
    const next = idx + dir;
    if (next < 0 || next >= blocks.length) return;
    const copy = [...blocks];
    const [item] = copy.splice(idx, 1);
    copy.splice(next, 0, item);
    onBlocksChange(copy);
  }

  function updateSelected(patch: Partial<QwebViewBlock>) {
    if (!selected) return;
    onBlocksChange(
      blocks.map((b) =>
        b.id === selected.id ? ({ ...b, ...patch } as QwebViewBlock) : b,
      ),
    );
  }

  function addBlock(kind: QwebViewBlock["kind"]) {
    const id = newQwebBlockId(kind);
    let block: QwebViewBlock;
    if (kind === "heading") {
      block = { id, kind: "heading", text: "Heading", level: 2 };
    } else if (kind === "field") {
      const field = insertField || fields[0]?.name || "display_name";
      block = { id, kind: "field", field };
    } else if (kind === "divider") {
      block = { id, kind: "divider" };
    } else {
      block = { id, kind: "paragraph", text: "New paragraph" };
    }
    onBlocksChange([...blocks, block]);
    setSelectedId(id);
  }

  async function handleSave() {
    let nextArch = arch;
    if (editorTab === "visual") {
      try {
        nextArch =
          strategy === "inherit"
            ? compileInheritFragment(blocks, {
                xpath: inheritXpath || "//div[hasclass('page')]",
                position: inheritPosition || "inside",
              })
            : compileQwebViewBlocks(blocks);
      } catch (err) {
        onError(err instanceof Error ? err.message : "Compile failed");
        return;
      }
    }
    const gate = refuseUnsafeQwebViewSave({
      arch: nextArch,
      blocks: editorTab === "visual" ? blocks : null,
      allowExistingTCalls: existingTCalls,
      inheritXpath: strategy === "inherit" ? inheritXpath : null,
      inheritPosition: strategy === "inherit" ? inheritPosition : null,
    });
    if (gate) {
      onError(gate);
      return;
    }
    if (editorTab === "visual") onArchChange(nextArch);
    await onSave();
  }

  if (!view) {
    return (
      <div className={styles.editorPane} data-testid="qweb-views-editor-empty">
        <div className={styles.emptyDesk}>
          <p className="p-6 text-sm text-muted">
            Select a QWeb view from the list, or create one above.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.editorPane} data-testid="qweb-views-editor">
      <div className={styles.editorToolbar}>
        <div className={styles.tabs} role="tablist" aria-label="Editor mode">
          <button
            type="button"
            role="tab"
            aria-selected={editorTab === "visual"}
            className={cn(styles.tab, editorTab === "visual" && styles.tabActive)}
            onClick={() => onEditorTabChange("visual")}
            disabled={!blocks.length && editorTab === "source"}
            data-testid="qweb-tab-paper"
          >
            Paper
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={editorTab === "source"}
            className={cn(styles.tab, editorTab === "source" && styles.tabActive)}
            onClick={() => {
              if (editorTab === "visual") {
                onArchChange(compileQwebViewBlocks(blocks));
              }
              onEditorTabChange("source");
            }}
            data-testid="qweb-tab-source"
          >
            Source XML
          </button>
        </div>
        <Button
          type="button"
          variant="primary"
          size="sm"
          loading={busy}
          disabled={!canMutate || busy}
          onClick={() => void handleSave()}
          data-testid="qweb-views-save"
          title={mutateBlocked || undefined}
        >
          Save
        </Button>
      </div>

      <div className={styles.editorBody}>
        {view.report_bound ? (
          <Callout variant="info" title="Also a report template" className="mb-3">
            Key {view.key} is bound to report {view.report_name || "—"}. Prefer the Reports
            studio for print layouts; this surface edits the same ir.ui.view arch.
          </Callout>
        ) : null}

        <div className="mb-3 grid gap-2 sm:grid-cols-3">
          <label className="text-sm">
            <span className="mb-1 block text-xs font-medium text-muted">Save strategy</span>
            <select
              className="w-full rounded-md border border-[color-mix(in_srgb,var(--ink)_12%,transparent)] bg-transparent px-2 py-1.5 text-sm"
              value={strategy}
              onChange={(e) => onStrategyChange(e.target.value as SaveStrategy)}
              data-testid="qweb-save-strategy"
            >
              <option value="inherit">Inherit (xpath child)</option>
              <option value="overwrite">Overwrite (advanced confirm)</option>
            </select>
          </label>
          <Input
            label="Inherit xpath"
            value={inheritXpath}
            onChange={(e) => onInheritXpathChange(e.target.value)}
            disabled={strategy !== "inherit"}
            className="font-mono"
            data-testid="qweb-inherit-xpath"
          />
          <label className="text-sm">
            <span className="mb-1 block text-xs font-medium text-muted">Position</span>
            <select
              className="w-full rounded-md border border-[color-mix(in_srgb,var(--ink)_12%,transparent)] bg-transparent px-2 py-1.5 text-sm"
              value={inheritPosition}
              disabled={strategy !== "inherit"}
              onChange={(e) => onInheritPositionChange(e.target.value)}
              data-testid="qweb-inherit-position"
            >
              <option value="inside">inside</option>
              <option value="before">before</option>
              <option value="after">after</option>
              <option value="replace">replace (refused if root)</option>
            </select>
          </label>
        </div>

        <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
          <ReportFieldPicker
            label={fieldsLoading ? "Fields (loading…)" : "Insert grounded t-field"}
            value={insertField}
            fields={fields}
            allowEmpty
            emptyLabel="— pick a field —"
            disabled={fieldsLoading || fields.length === 0 || !view.model}
            testId="qweb-field-picker"
            onChange={setInsertField}
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={!insertField || editorTab !== "visual"}
            onClick={() => addBlock("field")}
          >
            Insert field
          </Button>
        </div>

        {editorTab === "visual" ? (
          <>
            <div className="mb-2 flex flex-wrap gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => addBlock("heading")}>
                Add heading
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => addBlock("paragraph")}
              >
                Add paragraph
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => addBlock("divider")}>
                Add divider
              </Button>
            </div>
            <QwebPaperPreview
              title={view.name}
              keyLabel={view.key}
              model={view.model}
              bodyHtml={previewHtml}
            >
              <ReorderableBlocks
                items={blocks}
                getId={(b) => b.id}
                onMove={moveBlock}
                onReorder={(from, to) => {
                  onBlocksChange(moveIndex(blocks, from, to));
                }}
                className={styles.blocks}
                empty={
                  <p className="text-sm text-muted">
                    Empty document — add a heading, paragraph, divider, or grounded field. Foreign
                    arches open on Source XML.
                  </p>
                }
                listProps={{ "data-testid": "qweb-body-blocks" }}
              >
                {(block, _index, meta) => (
                  <button
                    type="button"
                    className={cn(
                      styles.block,
                      selectedId === block.id && styles.blockSelected,
                      meta.isDragging && "opacity-60",
                    )}
                    onClick={() => setSelectedId(block.id)}
                    data-testid={`qweb-block-${block.kind}`}
                  >
                    <span className="block text-[0.65rem] uppercase tracking-wide text-muted">
                      {block.kind}
                    </span>
                    {block.kind === "heading" || block.kind === "paragraph" ? (
                      <span className="text-sm">{block.text || "—"}</span>
                    ) : null}
                    {block.kind === "field" ? (
                      <span className="font-mono text-sm">doc.{block.field}</span>
                    ) : null}
                    {block.kind === "divider" ? <hr className="my-1 w-full" /> : null}
                    {block.kind === "locked" ? (
                      <pre className="max-h-16 overflow-auto text-[0.7rem] text-muted">
                        {block.locked_xml.slice(0, 160)}
                      </pre>
                    ) : null}
                  </button>
                )}
              </ReorderableBlocks>
            </QwebPaperPreview>
            {selected && (selected.kind === "heading" || selected.kind === "paragraph") ? (
              <div className="mt-3">
                <Input
                  label="Selected block text"
                  value={selected.text}
                  onChange={(e) => updateSelected({ text: e.target.value })}
                  data-testid="qweb-block-text"
                />
              </div>
            ) : null}
            {selected?.kind === "field" ? (
              <div className="mt-3">
                <Input
                  label="Field path"
                  value={selected.field}
                  className="font-mono"
                  onChange={(e) => updateSelected({ field: e.target.value })}
                  data-testid="qweb-block-field"
                />
              </div>
            ) : null}
          </>
        ) : (
          <>
            <Callout variant="warning" title="Source XML" className="mb-3">
              Foreign or complex arches stay here — no silent lossy rewrite. The shared unsafe gate
              still refuses script / t-raw / t-out / XXE / invent t-call / on* on save.
            </Callout>
            <QwebPaperPreview
              title={view.name}
              keyLabel={view.key}
              model={view.model}
              bodyHtml={previewHtml}
            />
            <textarea
              className="mt-3 min-h-[14rem] w-full rounded-md border border-[color-mix(in_srgb,var(--ink)_12%,transparent)] bg-transparent p-3 font-mono text-xs leading-relaxed"
              value={arch}
              onChange={(e) => onArchChange(e.target.value)}
              spellCheck={false}
              data-testid="qweb-source-xml"
              aria-label="QWeb source XML"
            />
            {existingTCalls.length ? (
              <p className="mt-2 text-xs text-muted" data-testid="qweb-grandfathered-tcalls">
                Grandfathered t-call targets: {existingTCalls.join(", ")}
              </p>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

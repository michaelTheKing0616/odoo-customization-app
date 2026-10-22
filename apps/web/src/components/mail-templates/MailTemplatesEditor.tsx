"use client";

import { useMemo, useState } from "react";
import { ReportFieldPicker } from "@/components/reports/ReportFieldPicker";
import {
  ReorderableBlocks,
  moveIndex,
} from "@/components/ui/canvas/ReorderableBlocks";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { FieldRow } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  compileMailBodyBlocks,
  newMailBlockId,
  type MailBodyBlock,
} from "./mailBodyBlocks";
import { MailPaperPreview } from "./MailPaperPreview";
import {
  formatMailPlaceholder,
  refuseUnsafeMailTemplate,
} from "./mailUnsafeGate";
import type { MailTemplateListRow } from "./MailTemplatesListPanel";
import styles from "./MailTemplatesPage.module.css";

type EditorTab = "visual" | "source";

type Props = {
  template: MailTemplateListRow | null;
  subject: string;
  emailTo: string;
  bodyHtml: string;
  blocks: MailBodyBlock[];
  fields: FieldRow[];
  fieldsLoading?: boolean;
  editorTab: EditorTab;
  busy?: boolean;
  canMutate?: boolean;
  mutateBlocked?: string | null;
  onSubjectChange: (v: string) => void;
  onEmailToChange: (v: string) => void;
  onBodyHtmlChange: (v: string) => void;
  onBlocksChange: (blocks: MailBodyBlock[]) => void;
  onEditorTabChange: (tab: EditorTab) => void;
  onSave: () => void | Promise<void>;
  onError: (msg: string) => void;
};

export function MailTemplatesEditor({
  template,
  subject,
  emailTo,
  bodyHtml,
  blocks,
  fields,
  fieldsLoading,
  editorTab,
  busy,
  canMutate = true,
  mutateBlocked,
  onSubjectChange,
  onEmailToChange,
  onBodyHtmlChange,
  onBlocksChange,
  onEditorTabChange,
  onSave,
  onError,
}: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [insertField, setInsertField] = useState("");

  const knownFields = useMemo(() => new Set(fields.map((f) => f.name)), [fields]);
  const selected = blocks.find((b) => b.id === selectedId) ?? null;

  const previewHtml =
    editorTab === "visual" ? compileMailBodyBlocks(blocks) : bodyHtml;

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

  function updateSelected(patch: Partial<MailBodyBlock>) {
    if (!selected) return;
    onBlocksChange(
      blocks.map((b) => (b.id === selected.id ? ({ ...b, ...patch } as MailBodyBlock) : b)),
    );
  }

  function addBlock(type: MailBodyBlock["type"]) {
    const id = newMailBlockId(type);
    let block: MailBodyBlock;
    if (type === "heading") {
      block = { id, type: "heading", text: "Heading", level: 2 };
    } else if (type === "field") {
      const field = insertField || fields[0]?.name || "display_name";
      block = { id, type: "field", field };
    } else {
      block = { id, type: "paragraph", text: "New paragraph" };
    }
    onBlocksChange([...blocks, block]);
    setSelectedId(id);
  }

  function insertPlaceholderIntoSource() {
    if (!insertField) return;
    const token = formatMailPlaceholder(insertField);
    onBodyHtmlChange(`${bodyHtml}${bodyHtml.endsWith("\n") || !bodyHtml ? "" : "\n"}${token}`);
  }

  async function handleSave() {
    const html = editorTab === "visual" ? compileMailBodyBlocks(blocks) : bodyHtml;
    const err = refuseUnsafeMailTemplate({
      subject,
      body_html: html,
      knownFields: fields.length ? knownFields : null,
    });
    if (err) {
      onError(err);
      return;
    }
    if (editorTab === "visual") onBodyHtmlChange(html);
    await onSave();
  }

  if (!template) {
    return (
      <div className={styles.editorPane} data-testid="mail-templates-editor-empty">
        <div className={styles.emptyDesk}>
          <p className="p-6 text-sm text-muted">
            Select a template from the list, or create one above.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.editorPane} data-testid="mail-templates-editor">
      <div className={styles.editorToolbar}>
        <div className={styles.tabs} role="tablist" aria-label="Editor mode">
          <button
            type="button"
            role="tab"
            aria-selected={editorTab === "visual"}
            className={cn(styles.tab, editorTab === "visual" && styles.tabActive)}
            onClick={() => onEditorTabChange("visual")}
          >
            Paper
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={editorTab === "source"}
            className={cn(styles.tab, editorTab === "source" && styles.tabActive)}
            onClick={() => {
              // Sync visual → source when leaving paper.
              if (editorTab === "visual") {
                onBodyHtmlChange(compileMailBodyBlocks(blocks));
              }
              onEditorTabChange("source");
            }}
          >
            Source HTML
          </button>
        </div>
        <Button
          type="button"
          variant="primary"
          size="sm"
          loading={busy}
          disabled={!canMutate || busy}
          onClick={() => void handleSave()}
          data-testid="mail-templates-save"
        >
          Save
        </Button>
      </div>

      <div className={styles.editorBody}>
        <div className="mb-3 grid gap-2 sm:grid-cols-2">
          <Input
            label="Subject"
            value={subject}
            onChange={(e) => onSubjectChange(e.target.value)}
            data-testid="mail-subject-input"
          />
          <Input
            label="Email to (expression)"
            value={emailTo}
            className="font-mono"
            onChange={(e) => onEmailToChange(e.target.value)}
            data-testid="mail-email-to-input"
          />
        </div>

        <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
          <ReportFieldPicker
            label={fieldsLoading ? "Fields (loading…)" : "Insert grounded field"}
            value={insertField}
            fields={fields}
            allowEmpty
            emptyLabel="— pick a field —"
            disabled={fieldsLoading || fields.length === 0}
            testId="mail-field-picker"
            onChange={setInsertField}
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={!insertField}
            onClick={() => {
              if (editorTab === "visual") addBlock("field");
              else insertPlaceholderIntoSource();
            }}
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
              <Button type="button" variant="ghost" size="sm" onClick={() => addBlock("paragraph")}>
                Add paragraph
              </Button>
            </div>
            <MailPaperPreview subject={subject} emailTo={emailTo} bodyHtml={previewHtml}>
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
                    Empty letter — add a heading, paragraph, or grounded field.
                  </p>
                }
                listProps={{ "data-testid": "mail-body-blocks" }}
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
                    data-testid={`mail-block-${block.id}`}
                  >
                    {block.type === "heading" ? (
                      <span className={block.level === 1 ? "text-lg font-semibold" : "font-semibold"}>
                        {block.text || "Heading"}
                      </span>
                    ) : null}
                    {block.type === "paragraph" ? (
                      <span>{block.text || "Paragraph"}</span>
                    ) : null}
                    {block.type === "field" ? (
                      <span className={styles.blockFieldChip}>
                        {formatMailPlaceholder(block.field)}
                      </span>
                    ) : null}
                  </button>
                )}
              </ReorderableBlocks>
            </MailPaperPreview>

            {selected ? (
              <div className={styles.inspector} data-testid="mail-block-inspector">
                <p className={styles.inspectorTitle}>Block · {selected.type}</p>
                {selected.type === "heading" || selected.type === "paragraph" ? (
                  <label className="mt-2 block text-xs">
                    Text
                    <input
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 text-sm"
                      value={selected.text}
                      onChange={(e) => updateSelected({ text: e.target.value })}
                    />
                  </label>
                ) : null}
                {selected.type === "field" ? (
                  <div className="mt-2">
                    <ReportFieldPicker
                      label="Field"
                      value={selected.field}
                      fields={fields}
                      testId="mail-block-field-picker"
                      onChange={(v) => updateSelected({ field: v })}
                    />
                  </div>
                ) : null}
                <div className="mt-2 flex gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => moveBlock(selected.id, -1)}
                  >
                    Up
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => moveBlock(selected.id, 1)}
                  >
                    Down
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      onBlocksChange(blocks.filter((b) => b.id !== selected.id));
                      setSelectedId(null);
                    }}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <>
            <MailPaperPreview subject={subject} emailTo={emailTo} bodyHtml={bodyHtml} />
            <label className="mt-3 block text-xs text-muted">
              Source HTML (gated on save — not a freeform ChatGPT editor)
              <textarea
                className={styles.codeArea}
                value={bodyHtml}
                onChange={(e) => onBodyHtmlChange(e.target.value)}
                data-testid="mail-body-source"
                spellCheck={false}
              />
            </label>
          </>
        )}
      </div>

      <div className={styles.editorFooter}>
        <span className="font-mono text-[0.625rem] text-muted">
          #{template.id} · {template.model || "—"}
        </span>
        {!canMutate && mutateBlocked ? (
          <span className="text-xs text-muted">{mutateBlocked}</span>
        ) : (
          <span className="text-xs text-muted">
            Online: placeholders render in Odoo send — preview chips here only.
          </span>
        )}
      </div>
    </div>
  );
}

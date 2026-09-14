"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type FieldRow, type LocatorIssue } from "@/lib/api";
import { fallbackWidgetsForTtype } from "@/lib/widgetCatalog";
import { isFragile, preferSemanticCandidates } from "@/lib/xpathLocator";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

type OverlayMessage = {
  type: string;
  fieldName?: string;
  tag?: string;
};

type Candidate = {
  xpath: string;
  match?: string;
  from_spec?: boolean;
  score?: number;
  fragile?: boolean;
  match_count?: number | null;
};

export type OverlayOperation =
  | "hide"
  | "move"
  | "relabel"
  | "add_field"
  | "set_widget"
  | "group_label";

type Props = {
  iframeRef: React.RefObject<HTMLIFrameElement | null>;
  connectionId: string;
  model: string;
  viewType: string;
  fields: FieldRow[];
  onSaved: (detail: { snapshotId?: string | null; viewId?: number | null }) => void;
  /** E2E harness only — synchronous selection without waiting for primary fetch. */
  selectionOverride?: { fieldName: string; xpath: string } | null;
};

const NOT_V1 = [
  "Add new model areas or notebook pages",
  "Complex multi-group restructures",
  "Kanban/card layout edits",
  "Search view filter logic",
];

const OPERATIONS: { id: OverlayOperation; label: string }[] = [
  { id: "hide", label: "Hide field" },
  { id: "move", label: "Move field" },
  { id: "relabel", label: "Edit label" },
  { id: "add_field", label: "Add field" },
  { id: "set_widget", label: "Set widget" },
  { id: "group_label", label: "Group / page label" },
];

export function OverlayEditor({
  iframeRef,
  connectionId,
  model,
  viewType,
  fields,
  onSaved,
  selectionOverride,
}: Props) {
  const [hover, setHover] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedXpath, setSelectedXpath] = useState<string>("");
  const [operation, setOperation] = useState<OverlayOperation>("hide");
  const [anchorField, setAnchorField] = useState("");
  const [movePosition, setMovePosition] = useState<"before" | "after">("after");
  const [label, setLabel] = useState("");
  const [placeholder, setPlaceholder] = useState("");
  const [helpText, setHelpText] = useState("");
  const [labelTarget, setLabelTarget] = useState<"field" | "group" | "page">("field");
  const [addFieldName, setAddFieldName] = useState("");
  const [addPosition, setAddPosition] = useState<"before" | "after" | "inside">("after");
  const [widget, setWidget] = useState("");
  const [xpathArch, setXpathArch] = useState("");
  const [xpathIssues, setXpathIssues] = useState<LocatorIssue[]>([]);
  const [xpathSuggested, setXpathSuggested] = useState<string | null>(null);
  const [primaryArch, setPrimaryArch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const fieldMeta = useMemo(
    () => fields.find((f) => f.name === selectedField),
    [fields, selectedField],
  );
  const widgetOptions = useMemo(
    () => fallbackWidgetsForTtype(fieldMeta?.ttype || "char"),
    [fieldMeta?.ttype],
  );

  const resolveSelection = useCallback(
    async (fieldName: string) => {
      setError(null);
      setSelectedField(fieldName);
      try {
        const primary = await api.getPrimaryView(connectionId, model, viewType);
        const parentArch = primary.arch ?? "";
        setPrimaryArch(parentArch);
        const resolved = await api.resolveFieldNode(connectionId, {
          view_type: viewType,
          arch: parentArch,
          field_name: fieldName,
        });
        const list = preferSemanticCandidates(resolved.candidates as Candidate[]);
        setCandidates(list);
        const first = list[0]?.xpath ?? `//field[@name='${fieldName}']`;
        setSelectedXpath(first);
        setAnchorField("");
        const meta = fields.find((f) => f.name === fieldName);
        setLabel(meta?.field_description ?? fieldName);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Resolve failed");
        setCandidates([]);
        setSelectedXpath(`//field[@name='${fieldName}']`);
      }
    },
    [connectionId, model, viewType, fields],
  );

  useEffect(() => {
    function onMessage(ev: MessageEvent<OverlayMessage>) {
      if (ev.source !== iframeRef.current?.contentWindow) return;
      const data = ev.data;
      if (!data || typeof data !== "object") return;
      if (data.type === "oc-overlay-hover" && data.fieldName) {
        setHover(data.fieldName);
      }
      if (data.type === "oc-overlay-select" && data.fieldName) {
        void resolveSelection(data.fieldName);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [iframeRef, resolveSelection]);

  const activeField = selectionOverride?.fieldName ?? selectedField;
  const activeXpath = selectionOverride?.xpath ?? selectedXpath;

  const applyBody = useMemo(() => {
    const anchorExpr = anchorField
      ? `//field[@name='${anchorField}']`
      : activeXpath;
    return {
      model,
      view_type: viewType,
      operation,
      expr: activeXpath,
      field_name: activeField ?? undefined,
      anchor_expr: operation === "move" || operation === "add_field" ? anchorExpr : undefined,
      move_position: operation === "move" ? movePosition : undefined,
      add_field_name: operation === "add_field" ? addFieldName : undefined,
      add_position: operation === "add_field" ? addPosition : undefined,
      string:
        operation === "relabel" || operation === "group_label" ? label : undefined,
      placeholder: operation === "relabel" && labelTarget === "field" ? placeholder : undefined,
      help_text: operation === "relabel" && labelTarget === "field" ? helpText : undefined,
      widget: operation === "set_widget" ? widget : undefined,
      label_target: operation === "relabel" ? labelTarget : undefined,
      parent_arch: primaryArch || undefined,
    };
  }, [
    addFieldName,
    addPosition,
    anchorField,
    helpText,
    label,
    labelTarget,
    model,
    movePosition,
    operation,
    placeholder,
    selectedField,
    selectedXpath,
    viewType,
    widget,
    activeField,
    activeXpath,
    primaryArch,
  ]);

  useEffect(() => {
    if (!activeField || !activeXpath) {
      setXpathArch("");
      setXpathIssues([]);
      return;
    }
    let cancelled = false;
    void api
      .overlayPreview(connectionId, applyBody)
      .then((res) => {
        if (cancelled) return;
        setXpathArch(res.xpath_arch);
        setXpathIssues(res.locator_issues ?? []);
        setXpathSuggested(res.suggested_expr ?? null);
      })
      .catch((err) => {
        if (cancelled) return;
        setXpathArch("");
        setXpathIssues([
          {
            severity: "error",
            code: "preview_failed",
            message: err instanceof Error ? err.message : "Preview failed",
          },
        ]);
      });
    return () => {
      cancelled = true;
    };
  }, [applyBody, connectionId, activeField, activeXpath]);

  async function onSave() {
    if (!activeField || !activeXpath) {
      setError("Select a field in the preview frame first.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.applyOverlayOp(connectionId, applyBody);
      setXpathArch(res.xpath_arch);
      setXpathIssues(res.locator_issues ?? []);
      setXpathSuggested(res.suggested_expr ?? null);
      setNotice(
        res.snapshot_id
          ? `Saved inherit #${res.view_id} — snapshot ${res.snapshot_id.slice(0, 8)}…`
          : `Saved inherit view #${res.view_id}`,
      );
      onSaved({ snapshotId: res.snapshot_id, viewId: res.view_id ?? null });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3 border-b border-border-subtle p-3" data-testid="overlay-editor">
      <Callout variant="info" title="Live overlay — v1 operations">
        Click a field in the preview frame, choose an operation, review xpath, then save as an
        inherit view (snapshot-first). Reloads the frame after save.
      </Callout>

      <div className="rounded-md border border-border-subtle bg-surface-muted p-3 text-sm">
        <p className="font-medium text-ink">Not in v1 — use View Designer instead</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
          {NOT_V1.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <Link
          href={`/connections/${connectionId}/designer?model=${encodeURIComponent(model)}`}
          className="mt-2 inline-block text-accent hover:underline"
        >
          Open View Designer
        </Link>
      </div>

      <p className="text-sm text-muted" data-testid="overlay-selected">
        {activeField ? (
          <>
            Selected: <code className="font-mono text-ink">{activeField}</code>
          </>
        ) : (
          <>No selection{hover ? ` — hover: ${hover}` : ""}</>
        )}
      </p>

      {candidates.length > 0 ? (
        <label className="block text-sm">
          <span className="text-muted">
            {candidates.length > 1 ? "Multiple nodes — pick a named locator" : "Locator"}
          </span>
          <select
            data-testid="overlay-xpath-picker"
            className="mt-1 w-full rounded-md border border-border-subtle bg-surface px-2 py-1.5 font-mono text-xs"
            value={selectedXpath}
            onChange={(e) => setSelectedXpath(e.target.value)}
          >
            {candidates.map((c) => (
              <option key={c.xpath} value={c.xpath}>
                {c.xpath}
                {c.fragile || isFragile(c.xpath) ? " · upgrade-fragile" : ""}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {activeXpath && isFragile(activeXpath) ? (
        <Callout variant="warning" title="This locator may break on upgrade" testId="overlay-fragile-hint">
          Prefer [@name] or [@id] when the parent view has a named alternative.
          {xpathSuggested && xpathSuggested !== activeXpath ? (
            <p className="mt-1">
              Named alternative:{" "}
              <button
                type="button"
                className="font-mono text-accent hover:underline"
                onClick={() => setSelectedXpath(xpathSuggested)}
              >
                {xpathSuggested}
              </button>
            </p>
          ) : null}
        </Callout>
      ) : null}

      <Select
        label="Operation"
        value={operation}
        onChange={(e) => setOperation(e.target.value as OverlayOperation)}
        options={OPERATIONS.map((op) => ({ value: op.id, label: op.label }))}
      />

      {operation === "move" || operation === "add_field" ? (
        <Select
          label={operation === "move" ? "Move relative to field" : "Anchor field"}
          value={anchorField}
          onChange={(e) => setAnchorField(e.target.value)}
          options={[
            { value: "", label: "Same as selected" },
            ...fields
              .filter((f) => f.name !== selectedField)
              .map((f) => ({ value: f.name, label: f.name })),
          ]}
        />
      ) : null}

      {operation === "move" ? (
        <Select
          label="Position"
          value={movePosition}
          onChange={(e) => setMovePosition(e.target.value as "before" | "after")}
          options={[
            { value: "before", label: "Before anchor" },
            { value: "after", label: "After anchor" },
          ]}
        />
      ) : null}

      {operation === "add_field" ? (
        <>
          <Select
            label="Field to add"
            value={addFieldName}
            onChange={(e) => setAddFieldName(e.target.value)}
            options={fields.map((f) => ({
              value: f.name,
              label: `${f.name} (${f.ttype})`,
            }))}
          />
          <Select
            label="Insert position"
            value={addPosition}
            onChange={(e) =>
              setAddPosition(e.target.value as "before" | "after" | "inside")
            }
            options={[
              { value: "after", label: "After anchor" },
              { value: "before", label: "Before anchor" },
              { value: "inside", label: "Inside anchor group" },
            ]}
          />
        </>
      ) : null}

      {operation === "relabel" ? (
        <>
          <Select
            label="Label target"
            value={labelTarget}
            onChange={(e) => setLabelTarget(e.target.value as "field" | "group" | "page")}
            options={[
              { value: "field", label: "Field label" },
              { value: "group", label: "Containing group" },
              { value: "page", label: "Notebook page" },
            ]}
          />
          <Input label="Label" value={label} onChange={(e) => setLabel(e.target.value)} />
          {labelTarget === "field" ? (
            <>
              <Input
                label="Placeholder"
                value={placeholder}
                onChange={(e) => setPlaceholder(e.target.value)}
              />
              <Input
                label="Help"
                value={helpText}
                onChange={(e) => setHelpText(e.target.value)}
              />
            </>
          ) : null}
        </>
      ) : null}

      {operation === "group_label" ? (
        <Input label="Group label" value={label} onChange={(e) => setLabel(e.target.value)} />
      ) : null}

      {operation === "set_widget" ? (
        <Select
          label="Widget"
          value={widget}
          onChange={(e) => setWidget(e.target.value)}
          options={[
            { value: "", label: "Choose widget" },
            ...widgetOptions.map((w) => ({ value: w.id, label: w.label })),
          ]}
        />
      ) : null}

      {xpathArch ? (
        <div data-testid="overlay-xpath-peek">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">
            Generated xpath
          </p>
          <CodeBlock code={xpathArch} language="xml" />
          {xpathIssues.some((i) => i.severity === "error") ? (
            <Callout
              variant="danger"
              title="Locator cannot be saved as-is"
              className="mt-2"
              testId="overlay-xpath-error"
            >
              {xpathIssues
                .filter((i) => i.severity === "error")
                .map((i) => i.message)
                .join(" ")}
            </Callout>
          ) : xpathIssues.some((i) => i.severity === "warning") ? (
            <p className="mt-1 text-xs text-warning" data-testid="overlay-xpath-warning">
              {xpathIssues
                .filter((i) => i.severity === "warning")
                .map((i) => i.message)
                .join(" ")}
            </p>
          ) : null}
        </div>
      ) : null}

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {notice ? <p className="text-sm text-success">{notice}</p> : null}

      <Button
        variant="primary"
        size="md"
        type="button"
        data-testid="overlay-save"
        disabled={
          busy ||
          !activeField ||
          xpathIssues.some((i) => i.severity === "error" && i.code !== "preview_failed")
        }
        loading={busy}
        onClick={() => void onSave()}
      >
        Save inherit xpath
      </Button>
    </div>
  );
}

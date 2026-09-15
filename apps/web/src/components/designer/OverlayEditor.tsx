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
import { OverlayHud } from "@/components/designer/OverlayHud";
import {
  OverlayStructurePicker,
  type StructureCandidate,
} from "@/components/designer/OverlayStructurePicker";

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
  | "group_label"
  | "add_page"
  | "add_group";

type Props = {
  iframeRef: React.RefObject<HTMLIFrameElement | null>;
  connectionId: string;
  model: string;
  viewType: string;
  fields: FieldRow[];
  onSaved: (detail: { snapshotId?: string | null; viewId?: number | null }) => void;
  /** E2E harness only — synchronous selection without waiting for primary fetch. */
  selectionOverride?: { fieldName: string; xpath: string } | null;
  /** Hide the standalone “open Designer” callout when already on Designer. */
  embedded?: boolean;
};

const NOT_V1 = [
  "Split, merge, or bulk-reorder groups across the form",
  "Kanban card templates, colors, and progress bars",
  "Search filter domains and group-by rows",
];

const ALL_OPERATIONS: { id: OverlayOperation; label: string; views: string[] }[] = [
  { id: "hide", label: "Hide field", views: ["form", "list", "kanban", "search"] },
  { id: "move", label: "Move field", views: ["form", "list", "kanban"] },
  { id: "relabel", label: "Edit label", views: ["form"] },
  { id: "add_field", label: "Add field", views: ["form", "list", "kanban", "search"] },
  { id: "set_widget", label: "Set widget", views: ["form"] },
  { id: "group_label", label: "Group / page label", views: ["form"] },
  { id: "add_page", label: "Add notebook page", views: ["form"] },
  { id: "add_group", label: "Add group", views: ["form"] },
];

function normalizeViewType(viewType: string): string {
  return viewType === "tree" ? "list" : viewType;
}

function operationsForView(viewType: string): { id: OverlayOperation; label: string }[] {
  const vt = normalizeViewType(viewType);
  return ALL_OPERATIONS.filter((op) => op.views.includes(vt)).map(({ id, label }) => ({
    id,
    label,
  }));
}

type MoveAnchorKind = "field" | "structure";

export function OverlayEditor({
  iframeRef,
  connectionId,
  model,
  viewType,
  fields,
  onSaved,
  selectionOverride,
  embedded = false,
}: Props) {
  const vt = normalizeViewType(viewType);
  const operations = useMemo(() => operationsForView(viewType), [viewType]);

  const [hover, setHover] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedXpath, setSelectedXpath] = useState<string>("");
  const [operation, setOperation] = useState<OverlayOperation>("hide");
  const [anchorField, setAnchorField] = useState("");
  const [moveAnchorKind, setMoveAnchorKind] = useState<MoveAnchorKind>("field");
  const [movePosition, setMovePosition] = useState<"before" | "after" | "inside">("after");
  const [label, setLabel] = useState("");
  const [structureLabel, setStructureLabel] = useState("New page");
  const [placeholder, setPlaceholder] = useState("");
  const [helpText, setHelpText] = useState("");
  const [labelTarget, setLabelTarget] = useState<"field" | "group" | "page">("field");
  const [addFieldName, setAddFieldName] = useState("");
  const [addPosition, setAddPosition] = useState<"before" | "after" | "inside">("after");
  const [widget, setWidget] = useState("");
  const [structureExpr, setStructureExpr] = useState("");
  const [structure, setStructure] = useState<StructureCandidate[]>([]);
  const [xpathArch, setXpathArch] = useState("");
  const [xpathIssues, setXpathIssues] = useState<LocatorIssue[]>([]);
  const [xpathSuggested, setXpathSuggested] = useState<string | null>(null);
  const [primaryArch, setPrimaryArch] = useState("");
  const [primaryLoading, setPrimaryLoading] = useState(true);
  const [primaryError, setPrimaryError] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
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
        setError(err instanceof Error ? err.message : "Could not resolve that field");
        setCandidates([]);
        setSelectedXpath(`//field[@name='${fieldName}']`);
      }
    },
    [connectionId, model, viewType, fields],
  );

  useEffect(() => {
    let cancelled = false;
    setPrimaryLoading(true);
    setPrimaryError(null);
    void api
      .getPrimaryView(connectionId, model, viewType)
      .then(async (primary) => {
        const arch = primary.arch ?? "";
        if (cancelled) return;
        setPrimaryArch(arch);
        const tags =
          vt === "kanban"
            ? ["kanban", "t"]
            : vt === "search"
              ? ["search"]
              : ["notebook", "page", "group", "sheet"];
        const resolved = await api.resolveStructure(connectionId, { arch, tags });
        if (cancelled) return;
        setStructure(preferSemanticCandidates(resolved.candidates));
      })
      .catch((err) => {
        if (cancelled) return;
        setPrimaryError(err instanceof Error ? err.message : "Could not load the parent view");
        setStructure([]);
      })
      .finally(() => {
        if (!cancelled) setPrimaryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, model, viewType, vt]);

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

  useEffect(() => {
    if (!operations.some((op) => op.id === operation)) {
      setOperation(operations[0]?.id ?? "hide");
    }
  }, [operations, operation]);

  const activeField = selectionOverride?.fieldName ?? selectedField;
  const activeXpath = selectionOverride?.xpath ?? selectedXpath;
  const structureOp = operation === "add_page" || operation === "add_group";
  const fieldlessAddField =
    operation === "add_field" && (vt === "kanban" || vt === "search") && !activeField;

  const notebookCandidates = useMemo(
    () => structure.filter((c) => c.tag === "notebook"),
    [structure],
  );
  const groupInjectCandidates = useMemo(
    () => structure.filter((c) => ["group", "page", "sheet", "notebook"].includes(c.tag)),
    [structure],
  );
  const moveStructureCandidates = useMemo(
    () => structure.filter((c) => ["group", "page"].includes(c.tag)),
    [structure],
  );
  const kanbanCandidates = useMemo(
    () => structure.filter((c) => c.tag === "kanban" || c.tag === "t"),
    [structure],
  );

  const applyExpr = useMemo(() => {
    if (structureOp) return structureExpr;
    if (fieldlessAddField) return structureExpr;
    return activeXpath;
  }, [structureOp, fieldlessAddField, structureExpr, activeXpath]);

  const applyAnchorExpr = useMemo(() => {
    if (operation === "move" && moveAnchorKind === "structure") {
      return structureExpr || undefined;
    }
    if (operation === "move" || operation === "add_field") {
      if (anchorField) return `//field[@name='${anchorField}']`;
      if (fieldlessAddField) return structureExpr || undefined;
      return activeXpath || undefined;
    }
    return undefined;
  }, [
    operation,
    moveAnchorKind,
    structureExpr,
    anchorField,
    fieldlessAddField,
    activeXpath,
  ]);

  const applyBody = useMemo(() => {
    const stringValue =
      operation === "relabel" || operation === "group_label"
        ? label
        : structureOp
          ? structureLabel
          : undefined;
    return {
      model,
      view_type: viewType,
      operation,
      expr: applyExpr,
      field_name: activeField ?? undefined,
      anchor_expr: applyAnchorExpr,
      move_position: operation === "move" ? movePosition : undefined,
      add_field_name:
        operation === "add_field" || structureOp ? addFieldName || undefined : undefined,
      add_position:
        fieldlessAddField
          ? "inside"
          : operation === "add_field" || operation === "add_group"
            ? addPosition
            : undefined,
      string: stringValue,
      placeholder: operation === "relabel" && labelTarget === "field" ? placeholder : undefined,
      help_text: operation === "relabel" && labelTarget === "field" ? helpText : undefined,
      widget: operation === "set_widget" ? widget : undefined,
      label_target: operation === "relabel" ? labelTarget : undefined,
      parent_arch: primaryArch || undefined,
    };
  }, [
    addFieldName,
    addPosition,
    applyAnchorExpr,
    applyExpr,
    helpText,
    label,
    labelTarget,
    model,
    movePosition,
    operation,
    placeholder,
    viewType,
    widget,
    activeField,
    primaryArch,
    structureLabel,
    structureOp,
    fieldlessAddField,
  ]);

  const canPreview = useMemo(() => {
    if (operation === "add_page" || operation === "add_group") {
      return Boolean(structureLabel.trim());
    }
    if (operation === "add_field") {
      return Boolean(addFieldName) && (Boolean(activeField && activeXpath) || fieldlessAddField);
    }
    if (operation === "move" && moveAnchorKind === "structure") {
      return Boolean(activeField && activeXpath && structureExpr);
    }
    return Boolean(activeField && activeXpath);
  }, [
    operation,
    structureLabel,
    addFieldName,
    activeField,
    activeXpath,
    fieldlessAddField,
    moveAnchorKind,
    structureExpr,
  ]);

  useEffect(() => {
    if (!canPreview) {
      setXpathArch("");
      setXpathIssues([]);
      setPreviewBusy(false);
      return;
    }
    let cancelled = false;
    setPreviewBusy(true);
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
            message: err instanceof Error ? err.message : "Could not preview this xpath",
          },
        ]);
      })
      .finally(() => {
        if (!cancelled) setPreviewBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applyBody, connectionId, canPreview]);

  function onOperationChange(next: OverlayOperation) {
    setOperation(next);
    setNotice(null);
    setError(null);
    if (next === "add_page") setStructureLabel((cur) => (cur === "New group" || !cur ? "New page" : cur));
    if (next === "add_group") setStructureLabel((cur) => (cur === "New page" || !cur ? "New group" : cur));
    if (next === "move") {
      setMoveAnchorKind("field");
      setMovePosition("after");
    }
    if (next === "add_group") setAddPosition("inside");
    if (next === "add_field" && (vt === "kanban" || vt === "search")) setAddPosition("inside");
  }

  async function onSave() {
    if (!canPreview) {
      setError(
        structureOp
          ? "Enter a page or group label first."
          : "Select a field in the preview frame first.",
      );
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
      setError(err instanceof Error ? err.message : "Could not save inherit xpath");
    } finally {
      setBusy(false);
    }
  }

  const blockingLocator = xpathIssues.some(
    (i) => i.severity === "error" && i.code !== "preview_failed",
  );
  const saveDisabled = busy || !canPreview || blockingLocator || (!xpathArch && !previewBusy);
  const selectedCandidate = candidates.find((c) => c.xpath === activeXpath);

  return (
    <div
      className={embedded ? "space-y-3" : "space-y-3 border-b border-border-subtle p-3"}
      data-testid="overlay-editor"
    >
      <Callout variant="info" title="Live overlay">
        Click a field in the live preview, choose an operation, review xpath, then save as an inherit
        view (snapshot-first). The frame reloads after save. Add page and add group work without a
        field selection.
      </Callout>

      {embedded ? null : (
        <div className="rounded-md border border-border-subtle bg-surface-muted p-3 text-sm">
          <p className="font-medium text-ink">Not in this overlay — use View Designer</p>
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
      )}

      <OverlayHud
        fieldName={activeField}
        ttype={fieldMeta?.ttype}
        xpath={activeXpath}
        matchCount={selectedCandidate?.match_count}
        hover={hover}
        loading={primaryLoading && !selectionOverride}
        loadError={selectionOverride ? null : primaryError}
      />

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
        hint="Verb-first inherit edits. Locators are checked against the parent view before save."
        value={operation}
        onChange={(e) => onOperationChange(e.target.value as OverlayOperation)}
        options={operations.map((op) => ({ value: op.id, label: op.label }))}
      />

      {operation === "add_page" ? (
        <>
          <OverlayStructurePicker
            label="Insert inside notebook"
            hint="If this form has no notebook, the inherit creates one on the sheet."
            candidates={notebookCandidates}
            value={structureExpr}
            onChange={setStructureExpr}
            emptyHint="No named notebook on this form — save will create one on the sheet."
            emptyLabel="Default notebook locator"
          />
          <Input
            label="Page label"
            value={structureLabel}
            onChange={(e) => setStructureLabel(e.target.value)}
          />
          <Select
            label="First field (optional)"
            value={addFieldName}
            onChange={(e) => setAddFieldName(e.target.value)}
            options={[
              { value: "", label: "Empty page" },
              ...fields.map((f) => ({
                value: f.name,
                label: `${f.name} (${f.ttype})`,
              })),
            ]}
          />
        </>
      ) : null}

      {operation === "add_group" ? (
        <>
          <OverlayStructurePicker
            label="Insert relative to"
            candidates={groupInjectCandidates}
            value={structureExpr}
            onChange={setStructureExpr}
            emptyLabel="Default named group or sheet"
          />
          <Select
            label="Position"
            value={addPosition}
            onChange={(e) =>
              setAddPosition(e.target.value as "before" | "after" | "inside")
            }
            options={[
              { value: "inside", label: "Inside anchor" },
              { value: "after", label: "After anchor" },
              { value: "before", label: "Before anchor" },
            ]}
          />
          <Input
            label="Group label"
            value={structureLabel}
            onChange={(e) => setStructureLabel(e.target.value)}
          />
          <Select
            label="First field (optional)"
            value={addFieldName}
            onChange={(e) => setAddFieldName(e.target.value)}
            options={[
              { value: "", label: "Empty group" },
              ...fields.map((f) => ({
                value: f.name,
                label: `${f.name} (${f.ttype})`,
              })),
            ]}
          />
        </>
      ) : null}

      {operation === "move" ? (
        <>
          <Select
            label="Move into"
            value={moveAnchorKind}
            onChange={(e) => {
              const kind = e.target.value as MoveAnchorKind;
              setMoveAnchorKind(kind);
              setMovePosition(kind === "structure" ? "inside" : "after");
            }}
            options={[
              { value: "field", label: "Another field" },
              { value: "structure", label: "A group or page" },
            ]}
          />
          {moveAnchorKind === "field" ? (
            <Select
              label="Move relative to field"
              value={anchorField}
              onChange={(e) => setAnchorField(e.target.value)}
              options={[
                { value: "", label: "Same as selected" },
                ...fields
                  .filter((f) => f.name !== selectedField)
                  .map((f) => ({ value: f.name, label: f.name })),
              ]}
            />
          ) : (
            <OverlayStructurePicker
              label="Target group or page"
              candidates={moveStructureCandidates}
              value={structureExpr}
              onChange={setStructureExpr}
              allowEmpty={false}
              emptyHint="No named group or page on this form — pick a field instead."
            />
          )}
          <Select
            label="Position"
            value={movePosition}
            onChange={(e) =>
              setMovePosition(e.target.value as "before" | "after" | "inside")
            }
            options={
              moveAnchorKind === "structure"
                ? [
                    { value: "inside", label: "Inside group or page" },
                    { value: "before", label: "Before group or page" },
                    { value: "after", label: "After group or page" },
                  ]
                : [
                    { value: "before", label: "Before anchor" },
                    { value: "after", label: "After anchor" },
                  ]
            }
          />
        </>
      ) : null}

      {operation === "add_field" ? (
        <>
          {vt === "form" ? (
            <Select
              label="Anchor field"
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
          {vt === "kanban" ? (
            <OverlayStructurePicker
              label="Card template"
              hint="Adds a field onto the card. Templates, colors, and progress bars stay in View Designer."
              candidates={kanbanCandidates}
              value={structureExpr}
              onChange={setStructureExpr}
              emptyLabel="Default card locator"
            />
          ) : null}
          {vt === "search" ? (
            <p className="text-xs text-muted">
              Adds a search field inside the search view. Filter domains stay in View Designer.
            </p>
          ) : null}
          <Select
            label="Field to add"
            value={addFieldName}
            onChange={(e) => setAddFieldName(e.target.value)}
            options={fields.map((f) => ({
              value: f.name,
              label: `${f.name} (${f.ttype})`,
            }))}
          />
          {vt === "form" || vt === "list" ? (
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
          ) : (
            <Select
              label="Insert position"
              value={addPosition}
              onChange={(e) =>
                setAddPosition(e.target.value as "before" | "after" | "inside")
              }
              options={[
                { value: "inside", label: "Inside card or search" },
                { value: "after", label: "After selected field" },
                { value: "before", label: "Before selected field" },
              ]}
            />
          )}
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

      {previewBusy && !xpathArch ? (
        <p className="text-xs text-muted" data-testid="overlay-preview-loading">
          Checking locators against the parent view
        </p>
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
          ) : (
            <p className="mt-1 text-xs text-muted">Named locators ready to save.</p>
          )}
        </div>
      ) : null}

      {error ? (
        <Callout variant="danger" title="Could not apply overlay">
          {error}
        </Callout>
      ) : null}
      {notice ? (
        <p className="text-sm text-success" data-testid="overlay-save-notice">
          {notice}
        </p>
      ) : null}

      <Button
        variant="primary"
        size="md"
        type="button"
        data-testid="overlay-save"
        disabled={saveDisabled}
        loading={busy}
        onClick={() => void onSave()}
      >
        Save inherit xpath
      </Button>
    </div>
  );
}

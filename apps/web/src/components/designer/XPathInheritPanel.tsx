"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { isFragile, isPositional } from "@/lib/xpathLocator";

export type LocatorIssue = {
  severity: "error" | "warning";
  code: string;
  message: string;
  expr?: string | null;
  suggestion?: string | null;
};

export type XPathPosition = "inside" | "after" | "before" | "replace" | "attributes";

type Props = {
  expr: string;
  position: XPathPosition;
  bodyXml: string;
  previewArch: string;
  issues: LocatorIssue[];
  suggestedExpr: string | null;
  defaultInjectExpr: string | null;
  matchCount: number | null;
  blocking: boolean;
  busy: boolean;
  model: string;
  hasOverride: boolean;
  onExprChange: (value: string) => void;
  onPositionChange: (value: XPathPosition) => void;
  onBodyChange: (value: string) => void;
  onPreview: () => void;
  onUseNamedLocator: (expr: string) => void;
  onUseAsOverride: () => void;
  onSave: () => void;
  onClearOverride: () => void;
};

const POSITIONS: { value: XPathPosition; label: string }[] = [
  { value: "inside", label: "Inside" },
  { value: "after", label: "After" },
  { value: "before", label: "Before" },
  { value: "replace", label: "Replace" },
  { value: "attributes", label: "Attributes" },
];

function titleForErrors(issues: LocatorIssue[]): string {
  if (issues.some((i) => i.code === "missing_node")) {
    return "Locator matches no node in the parent view";
  }
  if (issues.some((i) => i.code === "ambiguous_match")) {
    return "Locator matches more than one node";
  }
  if (issues.some((i) => i.code === "invalid_body_xml" || i.code === "invalid_xml")) {
    return "Inherit XML is not well-formed";
  }
  return "Locator cannot be saved as-is";
}

export function XPathInheritPanel({
  expr,
  position,
  bodyXml,
  previewArch,
  issues,
  suggestedExpr,
  defaultInjectExpr,
  matchCount,
  blocking,
  busy,
  model,
  hasOverride,
  onExprChange,
  onPositionChange,
  onBodyChange,
  onPreview,
  onUseNamedLocator,
  onUseAsOverride,
  onSave,
  onClearOverride,
}: Props) {
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");
  const named =
    suggestedExpr && suggestedExpr !== expr
      ? suggestedExpr
      : defaultInjectExpr && defaultInjectExpr !== expr
        ? defaultInjectExpr
        : null;
  const fragile = isFragile(expr);
  const positional = isPositional(expr);

  return (
    <div
      className="rounded-md border border-border-subtle bg-surface-raised shadow-subtle"
      data-testid="designer-xpath-panel"
    >
      <div className="border-b border-border-subtle px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
              XPath inherit
            </p>
            <p className="mt-1 text-xs text-muted">
              Named locators survive upgrades. Positional [n] does not.
            </p>
          </div>
          {positional ? (
            <Badge variant="warning">Positional</Badge>
          ) : fragile ? (
            <Badge variant="warning">Fragile</Badge>
          ) : (
            <Badge variant="success">Named</Badge>
          )}
        </div>
      </div>

      <div className="space-y-3 p-4">
        <Input
          label="Locator"
          hint="Prefer [@name] or [@id]. Avoid group[2] unless no named alternative exists."
          value={expr}
          onChange={(e) => onExprChange(e.target.value)}
          className="font-mono text-xs"
          data-testid="xpath-expr"
        />
        <Select
          label="Position"
          value={position}
          onChange={(e) => onPositionChange(e.target.value as XPathPosition)}
          options={POSITIONS}
        />
        <Textarea
          label="Body XML"
          hint="Inserted relative to the locator. Must be well-formed XML."
          value={bodyXml}
          onChange={(e) => onBodyChange(e.target.value)}
          rows={4}
          className="font-mono text-xs"
          data-testid="xpath-body"
        />

        {matchCount != null ? (
          <p className="text-xs text-muted" data-testid="xpath-match-count">
            {matchCount === 1
              ? "Matches one node in the loaded parent arch."
              : `Matches ${matchCount} nodes in the loaded parent arch.`}
          </p>
        ) : null}

        {named ? (
          <Callout
            variant="info"
            title="Named locator available"
            testId="xpath-named-suggestion"
            actions={
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => onUseNamedLocator(named)}
              >
                Use named locator
              </Button>
            }
          >
            <code className="font-mono text-xs text-ink">{named}</code>
          </Callout>
        ) : null}

        {errors.length > 0 ? (
          <Callout variant="danger" title={titleForErrors(errors)} testId="xpath-error-callout">
            <ul className="space-y-1">
              {errors.map((issue, i) => (
                <li key={`${issue.code}-${i}`}>
                  {issue.message}
                  {issue.suggestion ? (
                    <>
                      {" "}
                      <button
                        type="button"
                        className="text-accent hover:underline"
                        onClick={() => onUseNamedLocator(issue.suggestion as string)}
                      >
                        Use {issue.suggestion}
                      </button>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          </Callout>
        ) : null}

        {warnings.length > 0 ? (
          <Callout
            variant="warning"
            title="This locator may break on upgrade"
            testId="xpath-warning-callout"
          >
            <ul className="space-y-1">
              {warnings.map((issue, i) => (
                <li key={`${issue.code}-${i}`}>{issue.message}</li>
              ))}
            </ul>
          </Callout>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={busy}
            loading={busy}
            onClick={onPreview}
            data-testid="xpath-preview"
          >
            Preview locator
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={!previewArch}
            onClick={onUseAsOverride}
          >
            Use as arch override
          </Button>
          <Button
            type="button"
            size="sm"
            variant="primary"
            disabled={busy || !model || blocking || !previewArch}
            onClick={onSave}
            data-testid="xpath-save"
          >
            Save xpath inherit
          </Button>
          {hasOverride ? (
            <Button type="button" size="sm" variant="ghost" onClick={onClearOverride}>
              Clear override
            </Button>
          ) : null}
        </div>

        {blocking ? (
          <p className="text-xs text-danger" data-testid="xpath-save-blocked">
            Save is blocked until the locator matches exactly one parent node.
          </p>
        ) : null}

        {previewArch ? (
          <div data-testid="xpath-arch-preview">
            <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted">
              Inherit preview
            </p>
            <CodeBlock code={previewArch} language="xml" />
          </div>
        ) : null}
      </div>
    </div>
  );
}

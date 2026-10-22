"use client";

import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { Term } from "@/components/ui/Term";

type DraftStudioIdentityCardProps = {
  displayName: string;
  technicalPrefix: string;
  multiCompany: boolean;
  onDisplayName: (value: string) => void;
  onTechnicalPrefix: (value: string) => void;
  onMultiCompany: (value: boolean) => void;
};

export function DraftStudioIdentityCard({
  displayName,
  technicalPrefix,
  multiCompany,
  onDisplayName,
  onTechnicalPrefix,
  onMultiCompany,
}: DraftStudioIdentityCardProps) {
  return (
    <details className="draft-studio-disclosure draft-studio-identity" data-testid="draft-studio-identity">
      <summary>
        <span>Scaffold identity</span>
        <span className="draft-studio-disclosure-meta">
          {multiCompany ? "Multi-company" : displayName.trim() ? displayName.trim() : "Optional"}
        </span>
      </summary>
      <Card className="mt-3 space-y-4 p-5">
        <Input
          label="Display name"
          value={displayName}
          onChange={(e) => onDisplayName(e.target.value)}
          placeholder="e.g. Acme Library"
        />
        <Input
          label="Technical prefix (optional)"
          value={technicalPrefix}
          onChange={(e) => onTechnicalPrefix(e.target.value)}
          placeholder="e.g. lib_demo → x_lib_demo_book"
          hint="Omit for fixed template model names (library: x_lib_book, …)."
          className="font-mono"
        />
        <label className="flex max-w-md items-start gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={multiCompany}
            onChange={(e) => onMultiCompany(e.target.checked)}
            className="mt-1"
          />
          <span>
            <span className="font-medium">Multi-company aware</span>
            <span className="mt-0.5 block text-xs text-muted">
              Adds company field + <Term tech="ir.rule">record rules</Term> for template scaffold, Generate UI, and library export.
            </span>
          </span>
        </label>
      </Card>
    </details>
  );
}

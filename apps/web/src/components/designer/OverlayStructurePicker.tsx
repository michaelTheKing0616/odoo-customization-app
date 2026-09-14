"use client";

import { Select } from "@/components/ui/Select";
import { preferSemanticCandidates } from "@/lib/xpathLocator";

export type StructureCandidate = {
  xpath: string;
  tag: string;
  label: string;
  score?: number;
  fragile?: boolean;
  match_count?: number | null;
};

type Props = {
  label: string;
  hint?: string;
  candidates: StructureCandidate[];
  value: string;
  onChange: (xpath: string) => void;
  emptyHint?: string;
  allowEmpty?: boolean;
  emptyLabel?: string;
  testId?: string;
};

export function OverlayStructurePicker({
  label,
  hint,
  candidates,
  value,
  onChange,
  emptyHint,
  allowEmpty = true,
  emptyLabel = "Use default named locator",
  testId = "overlay-structure-picker",
}: Props) {
  const ranked = preferSemanticCandidates(candidates);
  if (!ranked.length) {
    return emptyHint ? (
      <p className="text-xs text-muted" data-testid={testId}>
        {emptyHint}
      </p>
    ) : null;
  }
  return (
    <Select
      label={label}
      hint={hint}
      data-testid={testId}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      options={[
        ...(allowEmpty ? [{ value: "", label: emptyLabel }] : []),
        ...ranked.map((c) => ({
          value: c.xpath,
          label: `${c.tag} · ${c.label}${c.fragile ? " · upgrade-fragile" : ""}`,
        })),
      ]}
    />
  );
}

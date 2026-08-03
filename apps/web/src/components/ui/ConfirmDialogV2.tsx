"use client";

import { ConfirmDialog, type ConfirmDialogProps } from "@/components/ConfirmDialog";

export type ConfirmDialogV2Props = ConfirmDialogProps & {
  riskLevel?: "standard" | "danger";
  snapshotNote?: string;
};

/**
 * Kit wrapper for phrase-confirm — backward-compatible with legacy ConfirmDialog callers.
 * Danger level appends snapshot guidance to the consequences list.
 */
export function ConfirmDialogV2({
  riskLevel = "standard",
  snapshotNote,
  risks,
  ...props
}: ConfirmDialogV2Props) {
  const mergedRisks =
    riskLevel === "danger" && snapshotNote ? [...risks, snapshotNote] : risks;
  return <ConfirmDialog {...props} risks={mergedRisks} />;
}

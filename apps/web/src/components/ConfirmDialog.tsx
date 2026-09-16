"use client";

import {
  ConfirmDialogV2,
  type ConfirmDialogV2Props,
} from "@/components/ui/ConfirmDialogV2";

export type ConfirmDialogProps = Omit<ConfirmDialogV2Props, "riskLevel"> & {
  riskLevel?: ConfirmDialogV2Props["riskLevel"];
};

/** @deprecated Import ConfirmDialogV2 directly. Kept as danger-default shim. */
export function ConfirmDialog({ riskLevel = "danger", ...props }: ConfirmDialogProps) {
  return <ConfirmDialogV2 riskLevel={riskLevel} {...props} />;
}

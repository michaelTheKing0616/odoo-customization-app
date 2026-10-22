"use client";

import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";

const CONFIRM_PHRASE = "I understand the risks";

type Props = {
  open: boolean;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (phrase: string) => void | Promise<void>;
};

export function ReportsDeleteConfirm({ open, busy, onCancel, onConfirm }: Props) {
  return (
    <ConfirmDialogV2
      open={open}
      riskLevel="danger"
      title="Delete report"
      warning="Removes the print action from this model."
      risks={["Users lose Print menu entry", "QWeb view may remain orphaned"]}
      phrase={CONFIRM_PHRASE}
      busy={busy}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />
  );
}

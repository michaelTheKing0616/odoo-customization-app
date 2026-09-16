"use client";

import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";

export type DesignerDangerConfirmsProps = {
  model: string;
  viewType: string;
  confirmPhrase: string;
  busy: boolean;
  confirmOverwriteOpen: boolean;
  setConfirmOverwriteOpen: (open: boolean) => void;
  confirmUnlinkInheritOpen: boolean;
  setConfirmUnlinkInheritOpen: (open: boolean) => void;
  confirmMutateOpen: boolean;
  setConfirmMutateOpen: (open: boolean) => void;
  onOverwrite: (phrase: string) => void;
  onUnlinkInherit: (phrase: string) => void;
  onMutateParent: (phrase: string) => void;
};

/** Phrase-gated danger confirms for overwrite / unlink inherit / mutate parent. */
export function DesignerDangerConfirms({
  model,
  viewType,
  confirmPhrase,
  busy,
  confirmOverwriteOpen,
  setConfirmOverwriteOpen,
  confirmUnlinkInheritOpen,
  setConfirmUnlinkInheritOpen,
  confirmMutateOpen,
  setConfirmMutateOpen,
  onOverwrite,
  onUnlinkInherit,
  onMutateParent,
}: DesignerDangerConfirmsProps) {
  return (
    <>
      <ConfirmDialogV2
        riskLevel="danger"
        open={confirmOverwriteOpen}
        title="Overwrite primary view"
        warning={`Mutate the live primary arch for ${model || "this model"} (not an inherit child). Prefer inherit when modules extend this view.`}
        risks={[
          "Can break stock xpath inherits (e.g. Contacts)",
          "Module upgrades may conflict",
          "Snapshot is taken — restore from published checkpoints when reversible",
        ]}
        blastRadius={[
          `Model ${model || "(unset)"}`,
          `View type ${viewType}`,
          "Primary ir.ui.view arch (overwrite)",
        ]}
        phrase={confirmPhrase}
        busy={busy}
        onCancel={() => setConfirmOverwriteOpen(false)}
        onConfirm={onOverwrite}
      />
      <ConfirmDialogV2
        riskLevel="danger"
        open={confirmUnlinkInheritOpen}
        title="Unlink designer inherit"
        warning={`Delete ${model || "model"}.designer.${viewType} — the Designer extension that can be removed without touching stock.`}
        risks={[
          "Removes the inherit child only (stock primary form stays)",
          "Custom groups that lived only in that inherit disappear",
          "Field inject views ({model}.custom.x_*.form) are not deleted",
          "A published checkpoint cannot recreate a deleted inherit view",
        ]}
        blastRadius={[
          `Inherit ${model || "model"}.designer.${viewType}`,
          "Designer extension view only",
        ]}
        phrase={confirmPhrase}
        busy={busy}
        onCancel={() => setConfirmUnlinkInheritOpen(false)}
        onConfirm={onUnlinkInherit}
      />
      <ConfirmDialogV2
        riskLevel="danger"
        open={confirmMutateOpen}
        title="Mutate parent view arch"
        warning="Mutating parent view arch overwrites existing module XML. Prefer inherit (default) for interop with installed modules."
        risks={[
          "Parent ir.ui.view arch is rewritten in place",
          "Module upgrades may conflict or overwrite your change",
          "Harder to uninstall cleanly than an extension view",
        ]}
        blastRadius={["Parent ir.ui.view arch", "In-place rewrite"]}
        phrase={confirmPhrase}
        busy={busy}
        onCancel={() => setConfirmMutateOpen(false)}
        onConfirm={onMutateParent}
      />
    </>
  );
}

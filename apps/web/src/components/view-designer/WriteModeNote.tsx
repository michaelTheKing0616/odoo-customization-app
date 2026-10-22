"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Note } from "./Note";
import { clearWriteRefusal, useWriteRefused } from "./writeModeSignal";

/** Read-only error state with a one-click way out. The switch still goes through the usual
 * typed confirmation, and the server still decides (only admins may change write mode). */
export function WriteModeNote({ connectionId, onSwitched }: { connectionId: string; onSwitched?: () => void }) {
  const refused = useWriteRefused();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!refused) return null;
  async function confirm() {
    setBusy(true);
    try {
      await api.updateConnectionWriteMode(connectionId, "standard");
      clearWriteRefusal();
      setAsking(false);
      toast.success("Write mode is on. Try your change again.");
      onSwitched?.();
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : "Couldn't switch to write mode.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Note tone="warning" as="div" role="alert" data-testid="vd-write-mode">
      <p>This connection is read-only, so Odoo didn&apos;t save the change.</p>
      <Button size="sm" onClick={() => setAsking(true)} data-testid="vd-write-mode-switch">Switch to write mode</Button>
      <ConfirmDialogV2
        open={asking}
        title="Switch to write mode?"
        warning="Ingenium will be allowed to change this Odoo database. Every change still needs your publish, keeps a backup and can be undone."
        risks={["Changes you publish reach real users of this database.", "Only workspace admins can do this."]}
        busy={busy}
        onConfirm={() => void confirm()}
        onCancel={() => setAsking(false)}
      />
    </Note>
  );
}

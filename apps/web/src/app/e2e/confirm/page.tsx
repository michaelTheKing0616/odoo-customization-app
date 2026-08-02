"use client";

import { useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const PHRASE = "I understand the risks";

export default function E2EConfirmHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  if (!enabled) {
    return <p>E2E harness disabled</p>;
  }

  return (
    <main className="p-8">
      <h1 className="mb-4 text-lg font-semibold">ConfirmDialog e2e harness</h1>
      <button
        type="button"
        data-testid="open-confirm"
        className="border px-4 py-2"
        onClick={() => {
          setResult(null);
          setOpen(true);
        }}
      >
        Open confirm
      </button>
      {result !== null && (
        <p data-testid="confirm-result" className="mt-4">
          {result}
        </p>
      )}
      <ConfirmDialog
        open={open}
        title="Destructive action"
        warning="This action cannot be undone."
        risks={["Data may be permanently deleted", "Rollback may be incomplete"]}
        phrase={PHRASE}
        onConfirm={() => {
          setOpen(false);
          setResult("confirmed:ok");
        }}
        onCancel={() => {
          setOpen(false);
          setResult("confirmed:cancelled");
        }}
      />
    </main>
  );
}

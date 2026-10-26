"use client";

import { Button } from "@/components/ui/Button";
import { toast } from "sonner";

/** Example harness for UI-F08 oracle Playwright. No API calls. */
export default function UiF08HarnessPage() {
  return (
    <main className="mx-auto max-w-md space-y-4 p-6" data-testid="ui-f08-harness">
      <h1 className="text-lg font-semibold text-ink">Toast checks</h1>
      <p className="text-sm text-ink-muted">Example page for Sonner accessibility checks.</p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={() => toast.success("Saved")}>Show success</Button>
        <Button type="button" onClick={() => toast.error("Something went wrong")}>
          Show error
        </Button>
      </div>
    </main>
  );
}

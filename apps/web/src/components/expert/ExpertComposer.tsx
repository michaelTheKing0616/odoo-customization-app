"use client";

import { Button } from "@/components/ui/Button";
import { Kbd } from "@/components/ui/layout-primitives";
import { expertComposerPlaceholder } from "@/lib/expert-journey";

type ExpertComposerProps = {
  value: string;
  onChange: (value: string) => void;
  errorPaste: string;
  onErrorPasteChange: (value: string) => void;
  errorInMainInput: boolean;
  busy?: boolean;
  onSubmit: () => void;
};

export function ExpertComposer({
  value,
  onChange,
  errorPaste,
  onErrorPasteChange,
  errorInMainInput,
  busy,
  onSubmit,
}: ExpertComposerProps) {
  return (
    <form
      className="expert-composer"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      {!errorInMainInput ? (
        <details className="expert-error-disclosure">
          <summary>Paste an error to diagnose</summary>
          <label className="sr-only" htmlFor="expert-error-paste">
            Paste an error to diagnose
          </label>
          <textarea
            id="expert-error-paste"
            className="expert-error-paste"
            rows={2}
            value={errorPaste}
            onChange={(e) => onErrorPasteChange(e.target.value)}
            placeholder="AccessError, KeyError, RPC traceback…"
            data-testid="expert-error-paste"
          />
        </details>
      ) : (
        <p className="mb-2 text-xs text-muted">Error details are included in your question below.</p>
      )}
      <textarea
        className="expert-input"
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            if (value.trim() && !busy) onSubmit();
          }
        }}
        placeholder={expertComposerPlaceholder()}
        data-testid="expert-input"
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <p className="text-[11px] text-muted">
          <Kbd>⌘</Kbd>
          <Kbd>↵</Kbd> to send. Expert never auto-promotes.
        </p>
        <Button type="submit" variant="primary" loading={busy} disabled={!value.trim()}>
          Ask Expert
        </Button>
      </div>
    </form>
  );
}

"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ChevronDown } from "@/components/ui/icons";
import { expertComposerPlaceholder } from "@/lib/expert-journey";

type ExpertComposerProps = {
  value: string;
  onChange: (value: string) => void;
  errorPaste: string;
  onErrorPasteChange: (value: string) => void;
  errorInMainInput: boolean;
  busy?: boolean;
  onSubmit: () => void;
  /** Bumped when something asks for the composer (top bar Expert, explain-this on the page). */
  focusNonce?: number;
  autoFocus?: boolean;
};

export function ExpertComposer({
  value,
  onChange,
  errorPaste,
  onErrorPasteChange,
  errorInMainInput,
  busy,
  onSubmit,
  focusNonce = 0,
  autoFocus,
}: ExpertComposerProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const pasteId = useId();
  const hintId = useId();
  const [pasteOpen, setPasteOpen] = useState(false);
  const showPaste = pasteOpen || Boolean(errorPaste.trim());

  useEffect(() => {
    if (focusNonce > 0) inputRef.current?.focus();
  }, [focusNonce]);

  useEffect(() => {
    if (autoFocus && window.matchMedia?.("(hover: hover) and (pointer: fine)").matches) {
      inputRef.current?.focus({ preventScroll: true });
    }
  }, [autoFocus]);

  const canSend = Boolean(value.trim()) && !busy;

  return (
    <form
      className="expert-composer"
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSubmit();
      }}
    >
      <div className="expert-composer-box">
        <label className="sr-only" htmlFor={`${pasteId}-input`}>
          Ask Odoo Expert
        </label>
        <textarea
          ref={inputRef}
          id={`${pasteId}-input`}
          className="expert-input"
          rows={3}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              if (canSend) onSubmit();
            }
          }}
          placeholder={expertComposerPlaceholder()}
          aria-describedby={hintId}
          data-testid="expert-input"
        />
        {errorInMainInput ? (
          <p className="expert-composer-note">Error details are included in your question.</p>
        ) : (
          <div className="expert-error-block" id={pasteId} hidden={!showPaste}>
            <label className="expert-error-label" htmlFor={`${pasteId}-paste`}>
              Paste an error to diagnose
            </label>
            <textarea
              id={`${pasteId}-paste`}
              className="expert-error-paste"
              rows={3}
              value={errorPaste}
              onChange={(e) => onErrorPasteChange(e.target.value)}
              placeholder="AccessError, KeyError, RPC traceback…"
              spellCheck={false}
              data-testid="expert-error-paste"
            />
          </div>
        )}
        <div className="expert-composer-row">
          {!errorInMainInput ? (
            <button
              type="button"
              className="expert-composer-tool"
              aria-expanded={showPaste}
              aria-controls={pasteId}
              onClick={() => setPasteOpen((open) => !open)}
              data-testid="expert-error-toggle"
            >
              {showPaste ? "Hide error log" : "Add an error log"}
              <ChevronDown className="expert-composer-tool-chevron h-3.5 w-3.5" aria-hidden />
            </button>
          ) : (
            <span />
          )}
          <div className="expert-composer-send">
            <p className="expert-composer-hint" id={hintId}>
              <kbd>⌘</kbd>
              <kbd>Enter</kbd> to send. Expert never publishes on its own.
            </p>
            <Button type="submit" variant="primary" loading={busy} disabled={!value.trim()}>
              Ask Expert
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}

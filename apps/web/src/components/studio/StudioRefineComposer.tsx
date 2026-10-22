"use client";

import { useEffect, type RefObject } from "react";
import { Spokes } from "@/components/loading-ui/spokes";
import { SuggestionChip } from "./SuggestionChip";

type StudioRefineComposerProps = {
  composerRef?: RefObject<HTMLTextAreaElement | null>;
  chips: string[];
  value: string;
  fieldPack: boolean;
  hostFormName: string;
  busy: boolean;
  onChange: (value: string) => void;
  onSubmit: (instruction?: string) => void;
};

export function StudioRefineComposer({
  composerRef,
  chips,
  value,
  fieldPack,
  hostFormName,
  busy,
  onChange,
  onSubmit,
}: StudioRefineComposerProps) {
  const canSend = !busy && value.trim().length >= 3;

  useEffect(() => {
    const el = composerRef?.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(Math.max(el.scrollHeight, 40), 160)}px`;
  }, [value, composerRef]);

  return (
    <div className="chat-composer chat-composer-sticky">
      {chips.length ? (
        <div className="studio-chip-row studio-refine-chips">
          {chips.map((chip) => (
            <SuggestionChip
              key={chip}
              label={chip}
              disabled={busy}
              onClick={() => onChange(chip)}
            />
          ))}
        </div>
      ) : null}
      <div className="chat-input-row">
        <textarea
          ref={composerRef}
          className="input chat-composer-input"
          rows={1}
          data-testid="studio-refine-composer"
          placeholder={
            fieldPack
              ? `Try “make the ${hostFormName.toLowerCase()} fields required”`
              : "Try “remove the priority field”"
          }
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={busy}
          aria-label="Describe a change"
          aria-describedby="studio-refine-hint"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && canSend) {
              e.preventDefault();
              onSubmit();
            }
          }}
        />
        <button
          type="button"
          className={`btn btn-sm chat-send${canSend ? " btn-primary" : " btn-secondary"}`}
          aria-label="Send change"
          disabled={!canSend}
          onClick={() => onSubmit()}
        >
          {busy ? <Spokes className="studio-loader-spokes" aria-hidden /> : "Send"}
        </button>
      </div>
      <p className="chat-composer-hint" id="studio-refine-hint">
        {busy
          ? "Updating the preview…"
          : canSend
            ? "Enter to send. Shift + Enter adds a new line."
            : "Type at least a few words to send a change."}
      </p>
    </div>
  );
}

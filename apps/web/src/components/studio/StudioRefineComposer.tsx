"use client";

import { Spokes } from "@/components/loading-ui/spokes";
import { SuggestionChip } from "./SuggestionChip";

type StudioRefineComposerProps = {
  chips: string[];
  value: string;
  fieldPack: boolean;
  hostFormName: string;
  busy: boolean;
  onChange: (value: string) => void;
  onSubmit: (instruction?: string) => void;
};

export function StudioRefineComposer({
  chips,
  value,
  fieldPack,
  hostFormName,
  busy,
  onChange,
  onSubmit,
}: StudioRefineComposerProps) {
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
          className="input chat-composer-input"
          rows={1}
          placeholder={
            fieldPack
              ? `Describe a change — e.g. make ${hostFormName.toLowerCase()} fields required`
              : "Describe a change — e.g. remove the priority field"
          }
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={busy}
          aria-label="Refine instruction"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && value.trim().length >= 3) {
              e.preventDefault();
              onSubmit();
            }
          }}
        />
        <button
          type="button"
          className="btn btn-primary btn-sm"
          aria-label="Send refinement"
          disabled={busy || value.trim().length < 3}
          onClick={() => onSubmit()}
        >
          {busy ? <Spokes className="studio-loader-spokes" aria-hidden /> : "Send"}
        </button>
      </div>
      <p className="chat-composer-hint">Enter to send · Shift+Enter for a new line</p>
    </div>
  );
}

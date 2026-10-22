"use client";

import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";

type ModelPickerProps = {
  model: string;
  onModelChange: (model: string) => void;
  onLoad: (e: FormEvent) => void;
  busy?: boolean;
};

/** Compact technical-name picker: one field, one secondary Load. */
export function AccessModelPicker({ model, onModelChange, onLoad, busy }: ModelPickerProps) {
  return (
    <form onSubmit={onLoad} className="flex items-end gap-2" data-testid="access-model-picker">
      <label className="ax-field" style={{ flex: "1 1 auto" }}>
        <span className="ax-field-label">Model</span>
        <input
          className="ax-input is-mono"
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          placeholder="res.partner"
          spellCheck={false}
          autoCapitalize="off"
          data-testid="access-model-input"
        />
      </label>
      <Button type="submit" variant="secondary" disabled={busy} loading={busy}>
        Load
      </Button>
    </form>
  );
}

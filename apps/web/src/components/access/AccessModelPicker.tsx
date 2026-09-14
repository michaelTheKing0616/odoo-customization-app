"use client";

import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

type ModelPickerProps = {
  model: string;
  onModelChange: (model: string) => void;
  onLoad: (e: FormEvent) => void;
  busy?: boolean;
};

export function AccessModelPicker({ model, onModelChange, onLoad, busy }: ModelPickerProps) {
  return (
    <form onSubmit={onLoad} className="space-y-2" data-testid="access-model-picker">
      <Input
        label="Model"
        value={model}
        onChange={(e) => onModelChange(e.target.value)}
        className="font-mono"
        hint="Technical name. Load to list ACL lines and record rules for that model."
      />
      <Button type="submit" variant="secondary" size="sm" disabled={busy} loading={busy}>
        Load model
      </Button>
    </form>
  );
}

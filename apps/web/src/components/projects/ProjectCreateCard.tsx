"use client";

import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

type ProjectCreateCardProps = {
  name: string;
  templateId: string;
  busy?: boolean;
  canSubmit?: boolean;
  submitBlockedReason?: string | null;
  onNameChange: (name: string) => void;
  onTemplateChange: (templateId: string) => void;
  onSubmit: (event: FormEvent) => void;
};

export function ProjectCreateCard({
  name,
  templateId,
  busy,
  canSubmit = true,
  submitBlockedReason,
  onNameChange,
  onTemplateChange,
  onSubmit,
}: ProjectCreateCardProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="projects-create">
      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">New draft</p>
          <h2 className="text-base font-semibold text-ink">Create a draft</h2>
          <p className="mt-1 text-sm text-muted">
            A draft is saved ModuleSpec history on this connection. Nothing writes to Odoo until
            Apply.
          </p>
        </div>
        <Input
          label="Name"
          required
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          hint="Shown on the release board and in ModuleSpec."
        />
        <Select
          label="Template"
          options={[
            { value: "library", label: "Library — portable ModuleSpec" },
            { value: "", label: "Blank" },
          ]}
          value={templateId}
          onChange={(event) => onTemplateChange(event.target.value)}
          hint="Library seeds book and loan models. Blank starts empty for ModuleSpec."
        />
        <Button
          type="submit"
          variant="primary"
          disabled={busy || !canSubmit || !name.trim()}
          title={submitBlockedReason ?? undefined}
          loading={busy}
          data-testid="projects-create-submit"
        >
          Create draft
        </Button>
      </Card>
    </form>
  );
}

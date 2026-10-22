"use client";

import type { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import type { ApprovalButton } from "@/lib/api";
import {
  PRIMARY_CTA,
  canDeployRule,
  type ApprovalRuleForm,
} from "@/lib/approvalScreen";

type ApprovalRuleComposerProps = {
  form: ApprovalRuleForm;
  buttons: ApprovalButton[];
  busy?: boolean;
  onChange: (next: Partial<ApprovalRuleForm>) => void;
  onDiscover: () => void;
  onDeploy: (e: FormEvent) => void;
};

export function ApprovalRuleComposer({
  form,
  buttons,
  busy,
  onChange,
  onDiscover,
  onDeploy,
}: ApprovalRuleComposerProps) {
  const ready = canDeployRule(form);
  return (
    <section className="ap-composer" id="approval-new-rule" data-testid="approval-rule-composer">
      <h2 className="ap-composer-title">New Odoo approval rule</h2>
      <p className="ap-composer-hint">
        Discover form buttons on a model, name the rule, pick an approver, then deploy it to the
        connection.
      </p>
      <form onSubmit={onDeploy} className="ap-composer-grid">
        <Input
          label="Model"
          value={form.model}
          onChange={(e) => onChange({ model: e.target.value })}
          autoComplete="off"
          data-testid="approval-rule-model"
        />
        <Input
          label="Rule name"
          value={form.name}
          onChange={(e) => onChange({ name: e.target.value })}
          autoComplete="off"
          data-testid="approval-rule-name"
        />
        <Select
          label="Button method"
          value={form.buttonMethod}
          onChange={(e) => onChange({ buttonMethod: e.target.value })}
          placeholder="Select a button"
          options={buttons.map((b) => ({
            value: b.name,
            label: b.label || b.name,
          }))}
          data-testid="approval-rule-button"
        />
        <Input
          label="Approver user id"
          value={form.approverUserId}
          onChange={(e) => onChange({ approverUserId: e.target.value })}
          inputMode="numeric"
          autoComplete="off"
          data-testid="approval-rule-approver"
        />
        <div className="ap-composer-actions" style={{ gridColumn: "1 / -1" }}>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onDiscover}
            disabled={busy || !form.model.trim()}
            data-testid="approval-discover-buttons"
          >
            Discover buttons
          </Button>
          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={busy || !ready}
            loading={busy}
            data-testid="approval-deploy-rule"
          >
            {PRIMARY_CTA}
          </Button>
        </div>
      </form>
    </section>
  );
}

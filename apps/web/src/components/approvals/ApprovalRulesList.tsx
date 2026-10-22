"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import type { ApprovalRule } from "@/lib/api";
import {
  filterApprovalRules,
  ruleMetaLine,
  rulesEmptyGuide,
} from "@/lib/approvalScreen";
import { ApprovalsStateGuide } from "./ApprovalsStateGuide";

type ApprovalRulesListProps = {
  rules: ApprovalRule[];
  loading?: boolean;
  busy?: boolean;
  query: string;
  testRecordId: string;
  onQueryChange: (query: string) => void;
  onTestRecordIdChange: (value: string) => void;
  onSimulate: (ruleId: string) => void;
  onOpenComposer: () => void;
};

export function ApprovalRulesList({
  rules,
  loading,
  busy,
  query,
  testRecordId,
  onQueryChange,
  onTestRecordIdChange,
  onSimulate,
  onOpenComposer,
}: ApprovalRulesListProps) {
  const filtered = filterApprovalRules(rules, query);
  const emptyGuide = rulesEmptyGuide(rules.length > 0 || Boolean(query.trim()), query.trim());

  return (
    <section className="ap-section" data-testid="approval-rules-section">
      <div className="ap-list-head">
        <h2 className="ap-list-title">Rules</h2>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={onOpenComposer}
          data-testid="approval-rules-new"
        >
          New rule
        </Button>
      </div>
      {rules.length > 0 || query ? (
        <input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Filter by name, model, or button"
          aria-label="Filter Odoo approval rules"
          data-testid="approval-rules-filter"
          className="ap-search"
        />
      ) : null}
      {loading ? (
        <div className="mt-3 space-y-2" data-testid="approval-rules-loading">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="mt-3">
          <ApprovalsStateGuide
            testId="approval-rules-empty"
            guide={emptyGuide}
            actions={
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={onOpenComposer}
                data-testid="approval-rules-empty-deploy"
              >
                Open new rule form
              </Button>
            }
          />
        </div>
      ) : (
        <ul className="ap-list">
          {filtered.map((rule) => (
            <li key={rule.id} data-testid={`approval-rule-row-${rule.id}`}>
              <div className="ap-list-row">
                <div className="min-w-0">
                  <p className="ap-list-name">{rule.name}</p>
                  <p className="ap-list-meta">{ruleMetaLine(rule)}</p>
                  <div className="ap-list-actions">
                    <input
                      className="ap-inline-input"
                      value={testRecordId}
                      onChange={(e) => onTestRecordIdChange(e.target.value)}
                      aria-label="Test record id"
                      data-testid={`approval-rule-record-${rule.id}`}
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={busy}
                      onClick={() => onSimulate(rule.id)}
                      data-testid={`approval-rule-simulate-${rule.id}`}
                    >
                      Simulate click
                    </Button>
                  </div>
                </div>
                <Badge variant={rule.deployed ? "success" : "warning"}>
                  {rule.deployed ? "Deployed" : "Draft"}
                </Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

import { Button } from "@/components/ui/Button";
import { DRY_RUN_CTA } from "@/lib/bulkSuiteScreen";
import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkMassEditSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="bu-panel-sub">
        One write per batch. Validates field types and protected-module policy before apply.
      </p>
      <label className="bu-field">
        Values (JSON object)
        <textarea
          rows={3}
          value={vm.valuesText}
          onChange={(e) => vm.setValuesText(e.target.value)}
        />
      </label>
      <div className="bu-actions">
        <Button
          type="button"
          variant="secondary"
          disabled={vm.busy}
          onClick={() => void vm.runMassEdit(true)}
        >
          {DRY_RUN_CTA} preview
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={vm.busy}
          onClick={() => void vm.runMassEdit(false)}
        >
          Apply mass edit
        </Button>
      </div>
    </>
  );
}

export function BulkDedupeSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="bu-panel-sub">
        Scan by field(s), pick a winner per group, relink inbound FKs, then archive losers.
      </p>
      {vm.scanResult?.partner_merge_available ? (
        <p className="bu-safe" data-tone="danger" data-testid="bulk-partner-merge-hint">
          Odoo partner merge wizard is available. Prefer it for res.partner on this instance.
        </p>
      ) : null}
      <label className="bu-field">
        Match fields (comma separated)
        <input
          className="font-mono"
          value={vm.matchFieldsText}
          onChange={(e) => vm.setMatchFieldsText(e.target.value)}
        />
      </label>
      <label className="bu-field">
        Mode
        <select
          value={vm.dedupeMode}
          onChange={(e) => vm.setDedupeMode(e.target.value as "exact" | "fuzzy")}
        >
          <option value="exact">Exact</option>
          <option value="fuzzy">Fuzzy (normalized / single-field clustering)</option>
        </select>
      </label>
      <div className="bu-actions">
        <Button type="button" variant="secondary" disabled={vm.busy} onClick={() => void vm.scanDedupe()}>
          Scan duplicates
        </Button>
      </div>
      {vm.scanResult && vm.scanResult.groups.length > 0 ? (
        <div className="mt-3 space-y-3 text-sm">
          <label className="bu-field">
            Duplicate group
            <select
              value={vm.selectedGroupIdx}
              onChange={(e) => {
                const idx = Number(e.target.value);
                vm.setSelectedGroupIdx(idx);
                const g = vm.scanResult?.groups[idx];
                if (g?.records[0]) vm.setWinnerId(g.records[0].id);
              }}
            >
              {vm.scanResult.groups.map((g, idx) => (
                <option key={g.group_key} value={idx}>
                  {g.group_key} ({g.records.length} records)
                </option>
              ))}
            </select>
          </label>
          {vm.selectedGroup ? (
            <fieldset className="space-y-2">
              <legend className="font-medium text-ink">Winner record</legend>
              {vm.selectedGroup.records.map((rec) => (
                <label key={rec.id} className="bu-inline">
                  <input
                    type="radio"
                    name="dedupe-winner"
                    checked={vm.winnerId === rec.id}
                    onChange={() => vm.setWinnerId(rec.id)}
                  />
                  <span>
                    {rec.display_name} (#{rec.id}) - {JSON.stringify(rec.preview)}
                  </span>
                </label>
              ))}
            </fieldset>
          ) : null}
          <div className="bu-actions">
            <Button
              type="button"
              variant="secondary"
              disabled={vm.busy || vm.winnerId == null}
              onClick={() => void vm.mergeDedupe(true)}
            >
              {DRY_RUN_CTA} merge
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={vm.busy || vm.winnerId == null}
              onClick={() => void vm.mergeDedupe(false)}
            >
              Merge group
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}

export function BulkActivitiesSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="bu-panel-sub">
        Schedule mail.activity rows on the selected model records (requires mail.activity.mixin).
      </p>
      {vm.activityProbe ? <p className="bu-safe">{vm.activityProbe}</p> : null}
      <div className="bu-field-grid bu-cols-2">
        <label className="bu-field">
          Activity type
          <select
            value={vm.activityTypeId}
            onChange={(e) => vm.setActivityTypeId(e.target.value)}
          >
            {vm.activityTypes.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="bu-field">
          Deadline (YYYY-MM-DD)
          <input
            value={vm.activityDeadline}
            onChange={(e) => vm.setActivityDeadline(e.target.value)}
            placeholder="2026-10-10"
          />
        </label>
        <label className="bu-field" style={{ gridColumn: "1 / -1" }}>
          Summary
          <input
            value={vm.activitySummary}
            onChange={(e) => vm.setActivitySummary(e.target.value)}
          />
        </label>
      </div>
      <div className="bu-actions">
        <Button type="button" variant="secondary" disabled={vm.busy} onClick={() => void vm.probeActivities()}>
          Probe model
        </Button>
        <Button type="button" variant="secondary" disabled={vm.busy} onClick={() => void vm.runActivities(true)}>
          {DRY_RUN_CTA}
        </Button>
        <Button type="button" variant="primary" disabled={vm.busy} onClick={() => void vm.runActivities(false)}>
          Schedule
        </Button>
      </div>
    </>
  );
}

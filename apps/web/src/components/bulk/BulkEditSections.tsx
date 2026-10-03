import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkMassEditSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="text-sm text-[var(--odoo-muted)]">
        One write per batch — validates field types and protected-module policy before apply.
      </p>
      <label className="block text-sm">
        Values (JSON object)
        <textarea
          className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-xs"
          rows={3}
          value={vm.valuesText}
          onChange={(e) => vm.setValuesText(e.target.value)}
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="odoo-btn-secondary"
          disabled={vm.busy}
          onClick={() => void vm.runMassEdit(true)}
        >
          Dry run preview
        </button>
        <button
          type="button"
          className="odoo-btn-primary"
          disabled={vm.busy}
          onClick={() => void vm.runMassEdit(false)}
        >
          Apply mass edit
        </button>
      </div>
    </>
  );
}

export function BulkDedupeSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="text-sm text-[var(--odoo-muted)]">
        Scan by field(s), pick a winner per group, relink inbound FKs, then archive losers.
      </p>
      {vm.scanResult?.partner_merge_available && (
        <p className="text-sm text-[var(--odoo-warning)]">
          Odoo partner merge wizard is available — prefer it for res.partner on this instance.
        </p>
      )}
      <label className="block text-sm">
        Match fields (comma separated)
        <input
          className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-sm"
          value={vm.matchFieldsText}
          onChange={(e) => vm.setMatchFieldsText(e.target.value)}
        />
      </label>
      <label className="block text-sm">
        Mode
        <select
          className="mt-1 border border-[var(--odoo-border)] bg-surface px-2 py-1.5"
          value={vm.dedupeMode}
          onChange={(e) => vm.setDedupeMode(e.target.value as "exact" | "fuzzy")}
        >
          <option value="exact">Exact</option>
          <option value="fuzzy">Fuzzy (normalized / single-field clustering)</option>
        </select>
      </label>
      <button
        type="button"
        className="odoo-btn-secondary"
        disabled={vm.busy}
        onClick={() => void vm.scanDedupe()}
      >
        Scan duplicates
      </button>
      {vm.scanResult && vm.scanResult.groups.length > 0 && (
        <div className="space-y-3 text-sm">
          <label className="block">
            Duplicate group
            <select
              className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5"
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
          {vm.selectedGroup && (
            <fieldset className="space-y-2">
              <legend>Winner record</legend>
              {vm.selectedGroup.records.map((rec) => (
                <label key={rec.id} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="dedupe-winner"
                    checked={vm.winnerId === rec.id}
                    onChange={() => vm.setWinnerId(rec.id)}
                  />
                  <span>
                    {rec.display_name} (#{rec.id}) —{" "}
                    {JSON.stringify(rec.preview)}
                  </span>
                </label>
              ))}
            </fieldset>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="odoo-btn-secondary"
              disabled={vm.busy || vm.winnerId == null}
              onClick={() => void vm.mergeDedupe(true)}
            >
              Dry run merge
            </button>
            <button
              type="button"
              className="odoo-btn-primary"
              disabled={vm.busy || vm.winnerId == null}
              onClick={() => void vm.mergeDedupe(false)}
            >
              Merge group
            </button>
          </div>
        </div>
      )}
    </>
  );
}

export function BulkActivitiesSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="text-sm text-[var(--odoo-muted)]">
        Schedule mail.activity rows on the selected model records (requires mail.activity.mixin).
      </p>
      {vm.activityProbe && (
        <p className="text-xs text-[var(--odoo-muted)]">{vm.activityProbe}</p>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block text-sm">
          Activity type
          <select
            className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5"
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
        <label className="block text-sm">
          Deadline (YYYY-MM-DD)
          <input
            className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5"
            value={vm.activityDeadline}
            onChange={(e) => vm.setActivityDeadline(e.target.value)}
            placeholder="2026-08-10"
          />
        </label>
        <label className="block text-sm md:col-span-2">
          Summary
          <input
            className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5"
            value={vm.activitySummary}
            onChange={(e) => vm.setActivitySummary(e.target.value)}
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="odoo-btn-secondary" disabled={vm.busy} onClick={() => void vm.probeActivities()}>
          Probe model
        </button>
        <button type="button" className="odoo-btn-secondary" disabled={vm.busy} onClick={() => void vm.runActivities(true)}>
          Dry run
        </button>
        <button type="button" className="odoo-btn-primary" disabled={vm.busy} onClick={() => void vm.runActivities(false)}>
          Schedule
        </button>
      </div>
    </>
  );
}

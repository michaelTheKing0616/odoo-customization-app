import { Button } from "@/components/ui/Button";
import {
  DISCOVER_CTA,
  DRY_RUN_CTA,
  PRIMARY_CTA,
  blastRadiusFromState,
  runBlockedReason,
} from "@/lib/bulkSuiteScreen";
import { BulkBlastRadius } from "./BulkBlastRadius";
import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkTransitionCard({ vm }: { vm: BulkSuitePageModel }) {
  const blast = blastRadiusFromState({
    model: vm.model,
    selectionMode: vm.selectionMode,
    idsText: vm.idsText,
    resultTotal: vm.result?.total,
    resultFailed: vm.result?.failed,
    dryRunResult: vm.result?.dry_run,
  });
  const blockReason = runBlockedReason({
    busy: vm.busy,
    method: vm.method,
    bulkSafe: vm.selectedButton ? vm.selectedButton.bulk_safe : null,
    selectionMode: vm.selectionMode,
    idsText: vm.idsText,
    domainText: vm.domainText,
  });

  return (
    <section className="bu-panel" data-testid="bulk-transition-panel" aria-labelledby="bulk-transition-title">
      <h2 id="bulk-transition-title" className="bu-panel-title">
        Workflow transition
      </h2>
      <p className="bu-panel-sub">
        Discover object buttons on the primary form view, select records, Test run the blast radius, then{" "}
        {PRIMARY_CTA}.
      </p>

      <div className="bu-field-grid bu-cols-2">
        <label className="bu-field">
          Model
          <input
            id="bulk-suite-model"
            className="font-mono"
            value={vm.model}
            onChange={(e) => vm.setModel(e.target.value)}
            list="bulk-suite-models"
          />
          <datalist id="bulk-suite-models">
            {vm.filteredModels.map((m) => (
              <option key={m.model} value={m.model}>
                {m.name}
              </option>
            ))}
          </datalist>
        </label>
        <label className="bu-field">
          Filter models
          <input
            value={vm.modelQuery}
            onChange={(e) => vm.setModelQuery(e.target.value)}
            placeholder="Search technical or label name"
          />
        </label>
      </div>

      <div className="bu-actions">
        <Button
          type="button"
          variant="secondary"
          disabled={vm.discoverBusy || !vm.model.trim()}
          loading={vm.discoverBusy}
          onClick={() => void vm.discover()}
        >
          {vm.discoverBusy ? "Discovering…" : DISCOVER_CTA}
        </Button>
      </div>

      {vm.buttons.length > 0 ? (
        <label className="bu-field mt-3">
          Transition method
          <select value={vm.method} onChange={(e) => vm.setMethod(e.target.value)}>
            {vm.buttons.map((b) => (
              <option key={b.name} value={b.name}>
                {b.bulk_safe ? "" : "! "}
                {b.label} ({b.name})
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {vm.selectedButton ? (
        <p
          className="bu-safe"
          data-tone={vm.selectedButton.bulk_safe ? undefined : "danger"}
          data-testid="bulk-safe-hint"
        >
          {vm.selectedButton.bulk_safe ? "Bulk-safe" : "Not bulk-safe"} - {vm.selectedButton.reason}
        </p>
      ) : null}

      <fieldset className="mt-3 space-y-2 text-sm">
        <legend className="font-medium text-ink">Record selection</legend>
        <label className="bu-inline mr-4">
          <input
            type="radio"
            checked={vm.selectionMode === "domain"}
            onChange={() => vm.setSelectionMode("domain")}
          />
          Domain
        </label>
        <label className="bu-inline">
          <input
            type="radio"
            checked={vm.selectionMode === "ids"}
            onChange={() => vm.setSelectionMode("ids")}
          />
          Explicit ids
        </label>
      </fieldset>

      {vm.selectionMode === "domain" ? (
        <label className="bu-field mt-2">
          Domain (JSON list, cap 1000)
          <textarea
            rows={3}
            value={vm.domainText}
            onChange={(e) => vm.setDomainText(e.target.value)}
          />
        </label>
      ) : (
        <label className="bu-field mt-2">
          Record ids (comma or space separated)
          <input
            className="font-mono"
            value={vm.idsText}
            onChange={(e) => vm.setIdsText(e.target.value)}
          />
        </label>
      )}

      <BulkBlastRadius blast={blast} />

      <div className="bu-actions">
        <Button
          type="button"
          variant="secondary"
          disabled={vm.busy || !vm.method}
          loading={vm.busy}
          onClick={() => void vm.run(true)}
        >
          {DRY_RUN_CTA}
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={vm.busy || Boolean(blockReason)}
          loading={vm.busy}
          data-testid="bulk-run-primary"
          onClick={() => void vm.run(false)}
        >
          {PRIMARY_CTA}
        </Button>
        {blockReason ? <p className="bu-primary-reason">{blockReason}</p> : (
          <p className="bu-primary-reason">
            Test run first so the blast radius is visible before any write.
          </p>
        )}
      </div>
    </section>
  );
}

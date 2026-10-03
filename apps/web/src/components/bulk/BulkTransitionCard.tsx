import { Card } from "@/components/ui/layout-primitives";
import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkTransitionCard({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <Card className="mt-6 space-y-4 p-4">
      <label className="block text-sm">
        Model
        <input
          id="bulk-suite-model"
          className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-sm"
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
      <label className="block text-sm">
        Filter models
        <input
          className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 text-sm"
          value={vm.modelQuery}
          onChange={(e) => vm.setModelQuery(e.target.value)}
          placeholder="Search technical or label name"
        />
      </label>
      <button
        type="button"
        className="odoo-btn-secondary"
        disabled={vm.discoverBusy || !vm.model.trim()}
        onClick={() => void vm.discover()}
      >
        {vm.discoverBusy ? "Discovering…" : "Discover transitions"}
      </button>

      {vm.buttons.length > 0 && (
        <label className="block text-sm">
          Transition method
          <select
            className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5"
            value={vm.method}
            onChange={(e) => vm.setMethod(e.target.value)}
          >
            {vm.buttons.map((b) => (
              <option key={b.name} value={b.name}>
                {b.bulk_safe ? "" : "⚠ "}
                {b.label} ({b.name})
              </option>
            ))}
          </select>
        </label>
      )}
      {vm.selectedButton && (
        <p
          className={`text-sm ${vm.selectedButton.bulk_safe ? "text-[var(--odoo-muted)]" : "text-[var(--odoo-danger)]"}`}
        >
          {vm.selectedButton.bulk_safe ? "Bulk-safe" : "Not bulk-safe"} — {vm.selectedButton.reason}
        </p>
      )}

      <fieldset className="space-y-2 text-sm">
        <legend className="font-medium">Record selection</legend>
        <label className="mr-4 inline-flex items-center gap-2">
          <input
            type="radio"
            checked={vm.selectionMode === "domain"}
            onChange={() => vm.setSelectionMode("domain")}
          />
          Domain
        </label>
        <label className="inline-flex items-center gap-2">
          <input
            type="radio"
            checked={vm.selectionMode === "ids"}
            onChange={() => vm.setSelectionMode("ids")}
          />
          Explicit ids
        </label>
      </fieldset>

      {vm.selectionMode === "domain" ? (
        <label className="block text-sm">
          Domain (JSON list, cap 1000)
          <textarea
            className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-xs"
            rows={3}
            value={vm.domainText}
            onChange={(e) => vm.setDomainText(e.target.value)}
          />
        </label>
      ) : (
        <label className="block text-sm">
          Record ids (comma or space separated)
          <input
            className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-sm"
            value={vm.idsText}
            onChange={(e) => vm.setIdsText(e.target.value)}
          />
        </label>
      )}

      <div className="flex flex-wrap gap-2 pt-2">
        <button
          type="button"
          className="odoo-btn-secondary"
          disabled={vm.busy || !vm.method}
          onClick={() => void vm.run(true)}
        >
          Dry run
        </button>
        <button
          type="button"
          className="odoo-btn-primary"
          disabled={vm.busy || !vm.method || (vm.selectedButton ? !vm.selectedButton.bulk_safe : false)}
          onClick={() => void vm.run(false)}
        >
          Execute
        </button>
      </div>
    </Card>
  );
}

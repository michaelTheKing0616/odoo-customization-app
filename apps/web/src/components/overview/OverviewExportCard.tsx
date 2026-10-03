"use client";

import {
  SandboxDeployStages,
  sandboxDeployCurrentIndex,
} from "@/components/shell/SandboxDeployStages";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Card } from "@/components/ui/layout-primitives";
import { InstanceFingerprintCard } from "@/components/overview/InstanceFingerprintCard";
import type { OverviewPageModel } from "./use-overview-page";

export function OverviewExportCard({ vm }: { vm: OverviewPageModel }) {
  return (
    <>
      <InstanceFingerprintCard connectionId={vm.connectionId} context="develop" />
      <Card id="overview-export-card" className="mt-8 p-5">
        <h2 className="text-xl font-semibold text-ink">Export, sandbox &amp; promote</h2>
        <p className="mt-1 text-sm text-muted">
          Package new <code className="font-mono text-accent">x_*</code> models and/or extensions to
          stock models (inherit) → sandbox → promote after validation + confirm.
        </p>
        <SandboxDeployStages
          currentIndex={sandboxDeployCurrentIndex({
            hasValidationId: Boolean(vm.validationId),
            promotedCount: vm.promoted.length,
            sandboxBusy: vm.exportBusy,
          })}
          deploymentPanel={vm.deploymentPanel}
          logTail={vm.sandboxLogTail}
          approximation={
            vm.sandboxApproximation
              ? vm.sandboxApproximation +
                (vm.shStagingSuggestion ? ` ${vm.shStagingSuggestion}` : "")
              : null
          }
        />
        {vm.storeReadiness ? (
          <div
            className="mt-4 rounded border border-border-subtle bg-surface/80 p-4 text-sm"
            data-testid="store-readiness-report"
          >
            <p className="font-medium text-ink">
              Store readiness — {vm.storeReadiness.message}
            </p>
            <p className="mt-1 text-xs text-muted">{vm.storeReadiness.disclaimer}</p>
            <ul className="mt-2 space-y-1 text-muted">
              {vm.storeReadiness.items.map((item) => (
                <li key={item.key}>
                  [{item.status}] {item.label}: {item.message}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {vm.migrationAssist?.eligible ? (
          <div
            className="mt-4 rounded border border-border-subtle bg-surface/80 p-4 text-sm"
            data-testid="migration-assist-panel"
          >
            <p className="font-medium text-ink">{vm.migrationAssist.title}</p>
            <p className="mt-2 text-muted">{vm.migrationAssist.body}</p>
            {vm.migrationAssist.unlocks.length > 0 ? (
              <ul className="mt-3 list-disc pl-5 text-muted">
                {vm.migrationAssist.unlocks.map((u) => (
                  <li key={u.key}>
                    {u.label}: {u.online_status} → {u.sh_status} — {u.reason}
                  </li>
                ))}
              </ul>
            ) : null}
            <p className="mt-2 text-xs text-muted">{vm.migrationAssist.disclaimer}</p>
            <div className="mt-2 flex flex-wrap gap-3">
              {vm.migrationAssist.docs_links.map((link) => (
                <a
                  key={link.url}
                  href={link.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-muted hover:underline"
                >
                  {link.label}
                </a>
              ))}
            </div>
          </div>
        ) : null}
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <Input
            label="Technical name"
            value={vm.techName}
            onChange={(e) => vm.setTechName(e.target.value)}
            className="w-48"
          />
          <Input
            label="Display name"
            value={vm.displayName}
            onChange={(e) => vm.setDisplayName(e.target.value)}
            className="w-56"
          />
          <Select
            label="Install mode"
            options={[
              { value: "python", label: "python (local Docker)" },
              { value: "data", label: "data (remote import)" },
            ]}
            value={vm.installMode}
            onChange={(e) => vm.setInstallMode(e.target.value as "python" | "data")}
          />
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={vm.includeExtensions}
              onChange={(e) => vm.setIncludeExtensions(e.target.checked)}
            />
            Include stock-model extensions
          </label>
          <Input
            label="Extend models"
            value={vm.extendModels}
            onChange={(e) => vm.setExtendModels(e.target.value)}
            placeholder="res.partner, sale.order"
            className="w-64 font-mono"
          />
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={vm.storeReadyExport}
              onChange={(e) => vm.setStoreReadyExport(e.target.checked)}
            />
            Apps Store packaging assist
          </label>
          <Button
            type="button"
            variant="secondary"
            disabled={vm.exportBusy}
            onClick={vm.onExportModule}
          >
            Download zip
          </Button>
          <Button
            type="button"
            variant="primary"
            loading={vm.exportBusy}
            disabled={vm.exportBusy}
            onClick={vm.onSandboxRun}
          >
            Sandbox install
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={vm.exportBusy || !vm.validationId}
            onClick={() => vm.setShowPromoteConfirm(true)}
          >
            Promote to connection
          </Button>
        </div>
        <div className="mt-4 w-full max-w-2xl">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-muted">Extra depends (peer / stock modules)</p>
            <button
              type="button"
              disabled={vm.exportBusy}
              onClick={() => vm.onSuggestDepends()}
              className="border border-border-subtle px-2 py-0.5 text-xs text-muted disabled:opacity-50"
            >
              Suggest depends
            </button>
          </div>
          {vm.selectedDepends.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {vm.selectedDepends.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => vm.toggleDepend(name)}
                  className="border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-xs text-muted"
                  title="Click to remove"
                >
                  {name} ×
                </button>
              ))}
            </div>
          )}
          <input
            value={vm.dependsQuery}
            onChange={(e) => vm.setDependsQuery(e.target.value)}
            placeholder="Search installed modules…"
            className="mt-2 w-full border border-border-subtle bg-surface px-3 py-2 text-sm"
          />
          <div className="mt-2 max-h-40 overflow-y-auto border border-border-subtle bg-surface/80">
            {vm.filteredInstalledModules.map((m) => {
              const checked = vm.selectedDepends.includes(m.name);
              return (
                <label
                  key={m.id}
                  className="flex cursor-pointer items-start gap-2 border-b border-border-subtle px-3 py-2 text-sm last:border-b-0 hover:bg-surface-raised/60"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => vm.toggleDepend(m.name)}
                    className="mt-1"
                  />
                  <span>
                    <span className="font-mono text-muted">{m.name}</span>
                    {m.shortdesc ? (
                      <span className="ml-2 text-muted">{m.shortdesc}</span>
                    ) : null}
                  </span>
                </label>
              );
            })}
            {vm.filteredInstalledModules.length === 0 && (
              <p className="px-3 py-2 text-xs text-muted">
                No installed modules match.
              </p>
            )}
          </div>
          <label className="mt-2 block text-sm">
            <span className="text-muted">
              Free-form depends (not in list)
            </span>
            <input
              value={vm.extraDepends}
              onChange={(e) => vm.setExtraDepends(e.target.value)}
              placeholder="peer_custom_mod, another_mod"
              className="mt-1 block w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
            />
          </label>
        </div>
        {vm.validationId && (
          <p className="mt-3 text-xs text-muted">
            Validated · {vm.validationId.slice(0, 8)}… · mode={vm.installMode} · local Docker
            uses filesystem for python; remote promote needs data mode.
          </p>
        )}
        {vm.showPromoteConfirm && (
          <div className="mt-4 border border-warning/40 bg-warning-subtle p-4">
            <p className="text-sm font-medium text-warning-strong">Promote risks</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-warning">
              <li>Live metadata changes on this Odoo connection</li>
              <li>Uninstall may not fully reverse data</li>
              <li>Only the sandbox-validated zip will be installed</li>
            </ul>
            <label className="mt-3 block text-sm">
              <span className="text-muted">
                Type <code className="text-warning-strong">I understand the risks</code>
              </span>
              <input
                value={vm.confirmPhrase}
                onChange={(e) => vm.setConfirmPhrase(e.target.value)}
                className="mt-1 w-full max-w-md border border-warning/40 bg-surface px-3 py-2 text-sm"
              />
            </label>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                disabled={vm.exportBusy}
                onClick={vm.onPromote}
                className="h-9 bg-warning px-4 text-sm font-semibold text-ink disabled:opacity-60"
              >
                Proceed
              </button>
              <button
                type="button"
                onClick={() => vm.setShowPromoteConfirm(false)}
                className="h-9 border border-warning/40 px-4 text-sm text-warning"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}

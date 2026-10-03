import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import { EMPTY_STATES } from "@/lib/copy-guide";
import { BulkRecipeChips } from "./BulkRecipeChips";
import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkSuiteChrome({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <PageHeader
        title="Bulk Suite"
        description="Discover form-view workflow buttons per model and run them in bulk with dry-run first. Runs as the connected Odoo user — partial failures are reported per record."
      />
      <VersionAwarenessBanner capabilities={vm.connection?.capabilities} />

      <Callout variant="info" title="Invoices & bills" className="mt-4" testId="bulk-suite-document-batch-link">
        CSV/XLSX invoice & bill intake lives on{" "}
        <a
          className="font-medium text-ink underline underline-offset-2"
          href={`/connections/${vm.connectionId}/journal?tab=invoices`}
        >
          Snapshots & Journal → Invoices & bills
        </a>
        . Same Batch OS runner as Journal batch — dry-run first; preview ≠ posted.
      </Callout>

      <Callout variant="info" title="Master data batch" className="mt-4" testId="bulk-suite-master-data-link">
        Partners & products CSV →{" "}
        <a
          className="font-medium text-ink underline underline-offset-2"
          href={`/connections/${vm.connectionId}/journal?tab=master`}
        >
          Snapshots & Journal → Master data
        </a>
        . Same Batch OS runner — map → dry-run → apply; preview ≠ written.
      </Callout>


      {(vm.showRecipes || true) ? (
        <BulkRecipeChips onPick={vm.applyRecipe} />
      ) : null}

      {vm.connection ? <FirstWriteInterstitial connection={vm.connection} /> : null}

      {vm.error ? <ErrorNotice message={vm.error} className="mt-4" /> : null}
      {vm.notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {vm.notice}
        </Callout>
      ) : null}

      {!vm.pageHydrated ? (
        <div className="mt-6" data-testid="bulk-suite-hero-loading">
          <Skeleton className="h-32 w-full" />
        </div>
      ) : !vm.result && !vm.busy ? (
        <div className="mt-6">
          <EmptyState
            title="Bulk operations"
            description={EMPTY_STATES.bulkSuite}
            action={
              <button
                type="button"
                className="odoo-btn-secondary text-sm"
                onClick={() => document.getElementById("bulk-suite-model")?.focus()}
              >
                Choose a model
              </button>
            }
          />
        </div>
      ) : null}
    </>
  );
}

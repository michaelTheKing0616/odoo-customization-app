import type { ReactNode } from "react";
import { Callout } from "@/components/ui/Callout";
import { Skeleton } from "@/components/ui/layout-primitives";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  bulkHonestyGuide,
  emptyBulkGuide,
  sanitizeBulkCopy,
  type BulkErrorContext,
} from "@/lib/bulkSuiteScreen";
import { OperateStudioBar } from "@/components/operate/OperateStudioBar";
import { BulkRecipeChips } from "./BulkRecipeChips";
import { BulkErrorNotice } from "./BulkErrorNotice";
import { BulkOpRail } from "./BulkOpRail";
import { BulkStateGuide } from "./BulkStateGuide";
import type { BulkSuitePageModel } from "./use-bulk-suite-page";
import type { BulkStepIndex } from "@/lib/bulkSuiteScreen";
import { FrameMeta } from "@/components/frame/FrameMeta";

export function BulkSuiteChrome({
  vm,
  step,
  errorContext = "run",
  children,
}: {
  vm: BulkSuitePageModel;
  step: BulkStepIndex;
  errorContext?: BulkErrorContext;
  children?: ReactNode;
}) {
  const showEmpty = vm.pageHydrated && !vm.result && !vm.busy && !vm.error;
  const honesty = bulkHonestyGuide();

  return (
    <div className="bu-pasteboard">
      <article className="bu-sheet">
        <header className="bu-masthead studio-bar-dark">
          <div className="bu-mast-copy">
            <FrameMeta />
            <h1 className="bu-title">{PAGE_TITLE}</h1>
            <p className="bu-lead">{sanitizeBulkCopy(PAGE_DESCRIPTION)}</p>
          </div>
        </header>

        <VersionAwarenessBanner capabilities={vm.connection?.capabilities} />
        <BulkOpRail step={step} />

        {/* Write risk is imminent on this desk: one compact studio bar, not twin Callouts. */}
        <OperateStudioBar
          testId="bulk-honesty-guide"
          tone="warning"
          title={honesty.title}
          why={honesty.why}
          next={honesty.next}
        />

        <nav
          className="bu-link-row"
          data-testid="bulk-suite-cross-links"
          aria-label="Related batch tools"
        >
          <a
            className="bu-cross-link"
            data-testid="bulk-suite-document-batch-link"
            href={`/connections/${vm.connectionId}/journal?tab=invoices`}
          >
            <span className="bu-cross-link-title">Invoices and bills</span>
            <span className="bu-cross-link-body">
              CSV/XLSX intake on Snapshots and Journal. Test run first; preview is not posted.
            </span>
          </a>
          <a
            className="bu-cross-link"
            data-testid="bulk-suite-master-data-link"
            href={`/connections/${vm.connectionId}/journal?tab=master`}
          >
            <span className="bu-cross-link-title">Master data batch</span>
            <span className="bu-cross-link-body">
              Partners and products CSV on Snapshots and Journal. Map, test run, then apply.
            </span>
          </a>
        </nav>

        <BulkRecipeChips onPick={vm.applyRecipe} />

        {vm.connection ? <FirstWriteInterstitial connection={vm.connection} /> : null}

        {vm.error ? (
          <BulkErrorNotice
            message={vm.error}
            context={errorContext}
            onDismiss={() => vm.setError(null)}
          />
        ) : null}
        {vm.notice ? (
          <Callout variant="info" title="Notice" testId="bulk-suite-notice">
            {vm.notice}
          </Callout>
        ) : null}

        {!vm.pageHydrated ? (
          <div data-testid="bulk-suite-hero-loading">
            <Skeleton className="h-32 w-full" />
          </div>
        ) : null}

        {showEmpty ? (
          <BulkStateGuide
            testId="bulk-empty-guide"
            tone="accent"
            guide={emptyBulkGuide()}
            actions={
              <button
                type="button"
                className="bu-recipe"
                onClick={() => document.getElementById("bulk-suite-model")?.focus()}
              >
                Choose a model
              </button>
            }
          />
        ) : null}

        <div className="bu-work" data-testid="bulk-suite-desk">
          {children}
        </div>
      </article>
    </div>
  );
}

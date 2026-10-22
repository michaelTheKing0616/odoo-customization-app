"use client";

import { ModelTierBadge } from "./ModelTierBadge";
import { designAppsToInstall } from "@/lib/design-preview";
import type { StudioAppDesign } from "@/lib/studio-session";
import { ReviewRefineLayout } from "./ReviewRefineLayout";
import { StudioApplyBar } from "./StudioApplyBar";
import { StudioChatThread } from "./StudioChatThread";
import { StudioHonestyBanners } from "./StudioHonestyBanners";
import { StudioOptionAPanel } from "./StudioOptionAPanel";
import { StudioCustomCodeEntry } from "./StudioCustomCodeEntry";
import { StudioPreviewPane } from "./StudioPreviewPane";
import { integrationPlanFromSession } from "@/lib/integration-plan";
import { StudioMobileTabs } from "./StudioMobileTabs";
import { StudioRefineComposer } from "./StudioRefineComposer";
import type { StudioPageModel } from "./use-studio-page";

export function StudioReviewSection(vm: StudioPageModel) {
  return (
    <div className="studio-review">
      <StudioHonestyBanners
        connectionId={vm.connectionId}
        applyNote={vm.applyNote}
        calloutTitle={vm.calloutTitle}
        odooAppUrl={vm.odooAppUrl}
        goldInspectHref={vm.goldCanOpenSettings ? vm.goldInspect?.href : null}
        goldInspectLabel={vm.goldCanOpenSettings ? vm.goldInspect?.label : null}
        artifactConsistent={vm.session?.artifact_consistent !== false}
        appIsLiveOnOdoo={vm.appIsLiveOnOdoo}
        stockReuse={vm.stockReuse}
        refuseClone={vm.refuseClone}
        goldOptionA={vm.goldOptionA}
        authoredOptionA={vm.authoredOptionA}
        fieldPack={vm.fieldPack}
        hostFormName={vm.hostFormName}
        liveAppName={vm.liveAppName}
        grammarCard={vm.grammarCard}
        surfaceFindings={vm.surfaceFindings}
        liveApplyBanner={vm.liveApplyBanner}
        unfinishedBanner={vm.unfinishedBanner}
        operatorSurface={vm.operatorSurface}
        placementRows={vm.placementRows}
        slotCatalog={vm.slotCatalog}
        stockApps={vm.stockApps}
        applyBlocked={vm.applyBlocked}
        refineBusy={vm.busy === "refine"}
        onPlaceField={(fieldLabel, phrase) =>
          void vm.submitRefine(`put ${fieldLabel} ${phrase}`)
        }
        contractScorecard={
          (
            vm.session?.artifact as {
              _contract_scorecard?: {
                pass?: boolean;
                blocking?: boolean;
                summary?: string | null;
                repairs?: string[];
              };
            } | null | undefined
          )?._contract_scorecard ?? null
        }
        onRepairExpert={() =>
          void vm.submitRefine(
            "Fix surface findings that block Install. Ground the app title in the operator brief " +
              "(never a placeholder like Contact extras). Keep inherit-only on the named built-in form: " +
              "no new home-screen app. Preserve Must-do wiring (reuse existing fields, pickings/transfers " +
              "surface, filters, light automation).",
          )
        }
      />

      {vm.session?.id ? (
        <StudioCustomCodeEntry
          connectionId={vm.connectionId}
          sessionId={vm.session.id}
          artifact={vm.session.artifact as Record<string, unknown> | null | undefined}
        />
      ) : null}

      <StudioOptionAPanel
        goldOptionA={vm.goldOptionA}
        authoredOptionA={vm.authoredOptionA}
        goldId={vm.goldId}
        goldHonesty={vm.goldHonesty}
        goldSettings={vm.goldSettings}
        goldHost={vm.goldHost}
        goldInspect={vm.goldInspect}
        goldNeedsInvoicing={Boolean(vm.goldNeedsInvoicing)}
        goldCanPromote={vm.goldCanPromote}
        goldCanOpenSettings={vm.goldCanOpenSettings}
        goldPromoted={vm.goldPromoted}
        authoringPassed={vm.authoringPassed}
        authoringRetryable={vm.authoringRetryable}
        hostInstallOffers={vm.hostInstallOffers}
        leftoverAuthoringFindings={vm.leftoverAuthoringFindings}
        isOdooOnline={Boolean(vm.isOdooOnline)}
        busy={vm.busy}
        onInstallInvoicing={() => vm.setInstallOpen(true)}
        onDownloadZip={() => void vm.downloadGoldZip()}
        onProveSandbox={() => void vm.proveGoldSandbox()}
        onRepairWithAi={() => void vm.repairGoldWithAi()}
        onPromote={() => vm.setPromoteOpen(true)}
        onRetryAuthoring={() => void vm.retryGeneration()}
        onReverify={() => void vm.reverifyAuthoringGate()}
        onInstallHost={(offer, phrase) => void vm.installAuthoredHostModule(offer, phrase)}
        openInOdooHref={!vm.goldOptionA && vm.goldPromoted ? vm.openInOdooUrl : null}
        openInOdooLabel={
          vm.hostForOpen ? `Open ${vm.hostFormName}` : "Open in Odoo"
        }
      />

      <StudioMobileTabs value={vm.mobileTab} onChange={vm.setMobileTab} />

      <ReviewRefineLayout
        mobileTab={vm.mobileTab}
        header={
          <div className="panel-header">
            <div className="breadcrumb">
              <span>{vm.appTitle}</span>
              <span className="breadcrumb-sep" aria-hidden>/</span>
              <span className="current">{vm.preview?.title || "Form preview"}</span>
            </div>
            <div className="studio-preview-toolbar">
              {/* View Designer and Open in Odoo live once, in the apply bar below. */}
              <ModelTierBadge
                provider={vm.session?.provider_used}
                fallbackUsed={vm.session?.fallback_used}
              />
            </div>
          </div>
        }
        preview={
          vm.contractMatchesCanvas ? (
            <StudioPreviewPane
              draft={vm.session?.artifact}
              preview={vm.preview}
              breadcrumb={vm.preview?.title || vm.appTitle}
              flashFieldId={vm.flashId}
              highlightedFieldIds={vm.highlightIds}
              integrationPlan={integrationPlanFromSession(vm.session)}
            />
          ) : (
            <p className="studio-preview-empty" data-testid="studio-canvas-identity-gate">
              Preview hidden: the draft title does not match the locked diagnosis. Confirm the
              diagnosis again or generate again so the preview and the contract use one draft.
            </p>
          )
        }
        chat={
          <StudioChatThread
            conversation={vm.session?.conversation}
            localRefineError={vm.localRefineError}
            refineBusy={vm.busy === "refine"}
            onReuse={(content) => vm.setRefineInput(content)}
            onUndo={(instruction) => void vm.submitRefine(instruction)}
            onFocusComposer={() => {
              vm.setMobileTab("chat");
              vm.refineComposerRef.current?.focus();
            }}
          />
        }
        chatInput={
          <StudioRefineComposer
            composerRef={vm.refineComposerRef}
            chips={vm.refineChips}
            value={vm.refineInput}
            fieldPack={vm.fieldPack}
            hostFormName={vm.hostFormName}
            busy={vm.busy === "refine"}
            onChange={vm.setRefineInput}
            onSubmit={(instruction) => void vm.submitRefine(instruction)}
          />
        }
        footer={
          <StudioApplyBar
            designerHref={vm.designerHref}
            designerModel={vm.designerModel}
            appIsLiveOnOdoo={vm.appIsLiveOnOdoo}
            fieldPack={vm.fieldPack}
            hostFormName={vm.hostFormName}
            liveAppName={vm.liveAppName}
            goldOptionA={vm.goldOptionA}
            authoredOptionA={vm.authoredOptionA}
            goldCanOpenSettings={vm.goldCanOpenSettings}
            goldInspect={vm.goldInspect}
            goldHostMessage={vm.goldHost?.message}
            openInOdooUrl={vm.openInOdooUrl}
            canApply={vm.canApply}
            stockReuse={vm.stockReuse}
            refuseClone={vm.refuseClone}
            surfaceBlocked={vm.surfaceBlocked}
            applyBlocked={vm.applyBlocked}
            busy={vm.busy}
            onApply={() => vm.setApplyOpen(true)}
            connectionId={vm.connectionId}
            appsToInstall={designAppsToInstall(
              ((vm.session?.artifact as { _app_design?: StudioAppDesign } | null | undefined)?._app_design) ?? null,
            )}
          />
        }
      />
    </div>
  );
}

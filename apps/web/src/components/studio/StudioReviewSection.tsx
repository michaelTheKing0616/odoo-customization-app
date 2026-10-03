"use client";

import { ModelTierBadge } from "./ModelTierBadge";
import { ReviewRefineLayout } from "./ReviewRefineLayout";
import { StudioApplyBar } from "./StudioApplyBar";
import { StudioChatThread } from "./StudioChatThread";
import { StudioHonestyBanners } from "./StudioHonestyBanners";
import {
  StudioOpenInOdoo,
  StudioOpenInViewDesigner,
} from "./StudioOpenLinks";
import { StudioOptionAPanel } from "./StudioOptionAPanel";
import { StudioPreviewPane } from "./StudioPreviewPane";
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
              "(never a placeholder like Contact extras). Keep inherit-only on the named stock host — " +
              "no new home-screen app. Preserve Must-do wiring (reuse existing fields, pickings/transfers " +
              "surface, filters, light automation).",
          )
        }
      />

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

      <div className="studio-chip-row studio-mobile-tabs">
        <button
          type="button"
          className={`chip ${vm.mobileTab === "preview" ? "is-selected" : ""}`}
          onClick={() => vm.setMobileTab("preview")}
        >
          Preview
        </button>
        <button
          type="button"
          className={`chip ${vm.mobileTab === "chat" ? "is-selected" : ""}`}
          onClick={() => vm.setMobileTab("chat")}
        >
          Refine
        </button>
      </div>

      <ReviewRefineLayout
        mobileTab={vm.mobileTab}
        header={
          <div className="panel-header">
            <div className="breadcrumb">
              <span>{vm.appTitle}</span>
              <span aria-hidden>›</span>
              <span className="current">{vm.preview?.title || "Form preview"}</span>
            </div>
            <div className="studio-preview-toolbar">
              <StudioOpenInViewDesigner {...vm.designerLinkProps} compact />
              <StudioOpenInOdoo {...vm.openLinkProps} />
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
            />
          ) : (
            <p className="studio-preview-empty" data-testid="studio-canvas-identity-gate">
              Canvas hidden — draft title does not match the locked Contract. Confirm
              Diagnosis again or Generate so one IR drives both.
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
          />
        }
      />
    </div>
  );
}

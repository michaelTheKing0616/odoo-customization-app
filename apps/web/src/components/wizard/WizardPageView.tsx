"use client";

import { useState } from "react";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { Callout } from "@/components/ui/Callout";
import { DraftStudioApplyBar } from "@/components/draft-studio/DraftStudioApplyBar";
import { DraftStudioHonestyBanners } from "@/components/draft-studio/DraftStudioHonestyBanners";
import { DraftStudioIdentityCard } from "@/components/draft-studio/DraftStudioIdentityCard";
import {
  DraftStudioMobileTabs,
  type DraftStudioMobileTab,
} from "@/components/draft-studio/DraftStudioMobileTabs";
import { DraftStudioPreviewPane } from "@/components/draft-studio/DraftStudioPreviewPane";
import { DraftStudioProgress } from "@/components/draft-studio/DraftStudioProgress";
import { DraftStudioPromptPanel } from "@/components/draft-studio/DraftStudioPromptPanel";
import { DraftStudioReviewLayout } from "@/components/draft-studio/DraftStudioReviewLayout";
import { DraftStudioScorecard } from "@/components/draft-studio/DraftStudioScorecard";
import { DraftStudioShell } from "@/components/draft-studio/DraftStudioShell";
import { DraftStudioTemplates } from "@/components/draft-studio/DraftStudioTemplates";
import { visibleDraftWarnings } from "@/lib/draft-job-outcome";
import { WIZARD_ONLINE_HONESTY } from "@/lib/wizard-ui";
import { WizardErrorNotice } from "./WizardErrorNotice";
import { downloadEliteZipBase64, templateScaffoldOpts } from "./wizard-helpers";
import type { WizardPageModel } from "./use-wizard-page";

export function WizardPageView(vm: WizardPageModel) {
  const [mobileTab, setMobileTab] = useState<DraftStudioMobileTab>("preview");
  const promptPanel = (
    <DraftStudioPromptPanel
      connectionId={vm.connectionId}
      nlPrompt={vm.nlPrompt}
      aiEnabled={vm.aiEnabled}
      aiProviderLabel={vm.aiProviderLabel}
      ollamaDetail={vm.ollamaDetail}
      grainOverride={vm.grainOverride}
      grainLabel={vm.grainLabel}
      jsonPasteOpen={vm.jsonPasteOpen}
      jsonPaste={vm.jsonPaste}
      jsonBusy={vm.busy && vm.aiBusyLabel === "Preparing JSON draft…"}
      busy={vm.busy}
      overlapFindings={vm.overlapFindings}
      overlapChoice={vm.overlapChoice}
      overlapBusy={vm.overlapBusy}
      overlapResolved={vm.overlapResolved}
      connectPoints={vm.connectPoints}
      needsConnectReview={vm.needsConnectReview}
      connectPointsApproved={vm.connectPointsApproved}
      connectReviewBusy={vm.connectReviewBusy}
      hostCandidates={vm.hostCandidates}
      gallery={vm.componentGallery}
      selectedGalleryId={vm.selectedGalleryId}
      showStudioBridge={Boolean(
        vm.operatorBrief?.ir_confidence === "low" ||
          vm.generationEngine?.needs_clarification?.question,
      )}
      hasDraft={Boolean(vm.aiDraft)}
      isFullAppGrain={vm.isFullAppGrain}
      showActions={vm.journey.id === "prompt"}
      applyBar={vm.applyBarProps}
      reuse={vm.reuseProps}
      onPromptChange={(value) => {
        vm.setNlPrompt(value);
        vm.setConnectPointsApproved(false);
        vm.setConnectPoints(null);
        vm.setOverlapFindings([]);
        vm.setOverlapChoice(null);
        vm.setOverlapFindingId(null);
      }}
      onToggleJson={() => vm.setJsonPasteOpen((v) => !v)}
      onJsonChange={vm.setJsonPaste}
      onLoadJson={() => void vm.onLoadPastedJson("paste")}
      onUploadJson={(file) => void vm.onLoadPastedJson("file", file)}
      onGrainChange={(value) => {
        vm.setGrainOverride(value);
        vm.setConnectPointsApproved(value === "full_app");
        vm.setConnectPoints(null);
      }}
      onOverlapUse={vm.onOverlapUse}
      onOverlapExtend={vm.onOverlapExtend}
      onOverlapBuildAnyway={(id) => vm.onOverlapBuildAnyway(id)}
      onConnectField={(key, value) => {
        vm.setConnectPoints({ ...(vm.connectPoints || {}), [key]: value });
        vm.setConnectPointsApproved(false);
      }}
      onApproveConnect={() => vm.setConnectPointsApproved(true)}
      onReviewConnect={() => void vm.onReviewConnectPoints()}
      onCheckOverlap={() => void vm.onCheckOverlap()}
      onSelectGallery={(c) => {
        vm.setSelectedGalleryId(c.id);
        vm.setNlPrompt(`Add ${c.name.toLowerCase()} to my ${c.host_slot.replace(".", " ")}s`);
        vm.setConnectPointsApproved(false);
        vm.setConnectPoints(null);
      }}
      onClear={vm.startNewDraft}
    />
  );

  return (
    <DraftStudioShell
      connectionId={vm.connectionId}
      connectionName={vm.connection?.name}
      journey={vm.journey}
      canvas={vm.journey.id === "review" || vm.journey.id === "apply"}
      hasDraft={Boolean(vm.aiDraft)}
      onStartNew={vm.startNewDraft}
    >
      <div className="draft-studio-notices">
        <VersionAwarenessBanner capabilities={vm.connection?.capabilities} />
        {vm.isOdooOnline ? (
          <Callout
            variant="warning"
            title={WIZARD_ONLINE_HONESTY.title}
            testId="wizard-online-honesty"
          >
            {WIZARD_ONLINE_HONESTY.body}
          </Callout>
        ) : null}
        {vm.error ? (
          <WizardErrorNotice
            message={vm.error}
            hasDraft={Boolean(vm.aiDraft)}
            onDismiss={() => vm.setError(null)}
          />
        ) : null}
      </div>
      {vm.journey.id === "prompt" ? (
        <>
          {promptPanel}
          <DraftStudioIdentityCard
            displayName={vm.displayName}
            technicalPrefix={vm.technicalPrefix}
            multiCompany={vm.multiCompany}
            onDisplayName={vm.setDisplayName}
            onTechnicalPrefix={vm.setTechnicalPrefix}
            onMultiCompany={vm.setMultiCompany}
          />
          <DraftStudioTemplates
            connectionId={vm.connectionId}
            connection={vm.connection}
            templates={vm.templates}
            selectedId={vm.selected?.id}
            result={vm.result}
            loading={vm.loading}
            onOpenTemplate={vm.openConfirm}
            templateScaffoldOpts={templateScaffoldOpts}
          />
        </>
      ) : null}

      {vm.journey.id === "enrich" ? (
        <DraftStudioProgress label={vm.aiBusyLabel || "Generating the draft…"} />
      ) : null}

      {(vm.journey.id === "review" || vm.journey.id === "apply") && vm.aiDraft ? (
        <div className="studio-review">
          <DraftStudioHonestyBanners
            connectionId={vm.connectionId}
            liveApplyBanner={vm.liveApplyBanner}
            unfinishedBanner={vm.unfinishedBanner}
            generateUiBlocked={vm.generateUiBlocked}
            aiNote={vm.aiNote}
            genUiResult={vm.genUiResult}
            odooAppUrl={vm.odooAppUrl}
            llmStatusBanner={vm.llmStatusBanner}
            llmStatusMode={vm.llmStatusMode}
            retryDisabled={vm.retryEnrichmentDisabled}
            showRetry={vm.retryAvailable}
            aiBusy={vm.aiBusy}
            operatorBrief={vm.operatorBrief}
            refuseClone={vm.refuseClone}
            refuseHonesty={vm.generationEngine?.honesty}
            generationHonesty={vm.generationEngine?.honesty}
            operatorSurface={vm.operatorSurface}
            stockReuse={vm.stockReuse}
            stockApps={vm.stockApps}
            jobAutopilotHref={vm.jobAutopilotHref}
            clarifyQuestion={vm.generationEngine?.needs_clarification?.question}
            clarifyOptions={vm.generationEngine?.needs_clarification?.options}
            clarifyDefaultId={vm.generationEngine?.needs_clarification?.default_id}
            draftNeedsRegenerate={vm.needsRegenerate}
            canDraft={vm.canDraftModule}
            warnings={visibleDraftWarnings(vm.aiWarnings)}
            authoredOptionA={vm.authoredOptionA}
            authoringPassed={vm.authoringPassed}
            hostInstallOffers={vm.hostInstallOffers}
            leftoverAuthoringFindings={vm.leftoverAuthoringFindings}
            isOdooOnline={Boolean(vm.isOdooOnline)}
            optionALines={vm.liveApply?.option_a ?? []}
            capabilityPrimaryOptionA={Boolean(vm.aiDraft._capability_primary_option_a)}
            goLiveReady={vm.goLiveReady}
            zipLocked={vm.zipLocked}
            optionAProveBusy={vm.optionAProveBusy}
            optionAProveNote={vm.optionAProveNote}
            computeSuggestions={
              Array.isArray(vm.aiDraft._compute_suggestions)
                ? (vm.aiDraft._compute_suggestions as Array<{ model?: string; message?: string }>)
                : []
            }
            refusals={vm.aiRefusals}
            snapshots={vm.draftCacheEntries}
            onRetryEnrichment={() => void vm.retryAiEnrichment()}
            onRegenerate={() => void vm.onDraftFromPrompt()}
            onStashJobBrief={() => vm.stashBriefForJobAutopilot()}
            onInstallHost={(offer, phrase) => void vm.installAuthoredHostModule(offer, phrase)}
            onProveOptionA={() => void vm.proveOptionASandbox()}
            onRestoreSnapshot={(id) => void vm.restoreDraftFromCache(id)}
            onLoadWalkthrough={() => vm.setWalkthroughConfirmOpen(true)}
            onAnswerClarify={(answer) => vm.answerClarification(answer)}
          />
          <DraftStudioMobileTabs value={mobileTab} onChange={setMobileTab} />
          <DraftStudioReviewLayout
            mobileTab={mobileTab}
            header={
              <div className="panel-header">
                <div className="breadcrumb">
                  <span>{String(vm.aiDraft.display_name || vm.aiDraft.technical_name || "Draft")}</span>
                  <span aria-hidden>›</span>
                  <span className="current">{vm.residualPreview?.title || "Form preview"}</span>
                </div>
              </div>
            }
            preview={
              <DraftStudioPreviewPane
                connectionId={vm.connectionId}
                draft={vm.aiDraft}
                preview={vm.residualPreview}
                optionASettings={vm.optionASettings}
                stockReuse={vm.stockReuse}
                stockApps={vm.stockApps}
                nlPrompt={vm.nlPrompt}
              />
            }
            chrome={
              <DraftStudioScorecard
                scorecard={vm.scorecard}
                certification={vm.certification}
                certTierDisplay={vm.certTierDisplay}
                certShipReady={vm.certShipReady}
                doneBar={vm.doneBar}
                goLiveReady={vm.goLiveReady}
                stockReuse={vm.stockReuse}
                isComponent={Boolean(vm.aiDraft._component)}
                refuseClone={vm.refuseClone}
                aiBusy={vm.aiBusy}
                hasDraft
                expertHint={vm.expertHint}
                eliteBusy={vm.eliteBusy}
                eliteLintOk={vm.eliteLintOk}
                eliteLintNote={vm.eliteLintNote}
                eliteValidationId={vm.eliteValidationId}
                eliteZipBase64={vm.eliteZipBase64}
                eliteNote={vm.eliteNote}
                expertReviewNote={vm.expertReviewNote}
                expertReviewFindings={vm.expertReviewFindings}
                finisherComplete={vm.finisherComplete}
                draftSummary={vm.draftSummary}
                isOdooOnline={Boolean(vm.isOdooOnline)}
                jobAutopilotHref={vm.jobAutopilotHref}
                onExpertFix={() => void vm.askExpertReviewDraft(true)}
                onLint={() => void vm.refreshEliteLint()}
                onValidate={() => void vm.onEliteValidateModule()}
                onPromote={() => vm.setElitePromoteConfirmOpen(true)}
                onDownloadValidatedZip={() =>
                  downloadEliteZipBase64(
                    String(vm.aiDraft?.technical_name || "custom_module"),
                    vm.eliteZipBase64 || "",
                  )
                }
                onAskExpert={() =>
                  vm.openExpert({
                    question: `Review this draft module spec for production readiness: ${vm.draftSummary ?? "module"}. What should I verify before publish?`,
                    freshThread: true,
                  })
                }
              />
            }
            footer={<DraftStudioApplyBar {...vm.applyBarProps} />}
          />
          <details className="draft-studio-disclosure draft-studio-adjust" data-testid="draft-studio-adjust">
            <summary>
              <span>Adjust the prompt</span>
              <span className="draft-studio-disclosure-meta">Reuse, grain, JSON</span>
            </summary>
            <div className="mt-3">{promptPanel}</div>
          </details>
        </div>
      ) : null}

      <ConfirmDialogV2
        riskLevel="danger"
        open={vm.confirmOpen}
        title={`Scaffold ${vm.selected?.name ?? "app"}`}
        warning="This creates models, fields, and views on the live Odoo connection."
        risks={[
          "Live metadata writes on this connection",
          "May create multiple x_* models and ACL rows",
          "Existing models with the same name are skipped or extended",
          ...(vm.multiCompany
            ? ["Adds x_company_id + multi-company record rules on workflow models"]
            : []),
        ]}
        phrase={vm.confirmPhrase}
        busy={vm.busy}
        onCancel={() => vm.setConfirmOpen(false)}
        onConfirm={vm.onConfirmScaffold}
      />
      <ConfirmDialogV2 riskLevel="danger"
        open={vm.genUiConfirmOpen}
        title="Apply draft to Odoo"
        warning="Applies the App plan draft: models, fields, views, menus, and smart buttons on this live Odoo connection."
        risks={[
          "Creates ir.model / fields / views / menus",
          "May rewrite primary form arches for custom x_* models (statusbars)",
          "Smart buttons use extension views, so built-in forms like Contacts stay intact",
          "Automations in the draft are listed only. Create them on the Automations page",
          "Try a test copy before changing production",
          ...(vm.validateLiveResult && !vm.validateLiveResult.ok
            ? [
                `Validate-live: ${vm.validateLiveResult.fail_count} failure(s). Override only if you accept broken metadata risk`,
              ]
            : []),
        ]}
        phrase={vm.confirmPhrase}
        busy={vm.busy}
        onCancel={() => {
          vm.setGenUiConfirmOpen(false);
          vm.setSkipValidateLive(false);
        }}
        onConfirm={(phrase) => {
          const forceSkip = Boolean(vm.validateLiveResult && !vm.validateLiveResult.ok);
          void vm.onGenerateUiFromDraft(phrase, forceSkip);
        }}
      />
      <ConfirmDialogV2 riskLevel="danger"
        open={vm.elitePromoteConfirmOpen}
        title="Publish validated module"
        warning="Installs the sandbox-validated Python module on this live Odoo connection."
        risks={[
          "Adds models, fields, views, Python code, reports, and cron jobs",
          "Uninstall may not fully reverse data",
          "Only promote after sandbox validation passed",
        ]}
        phrase={vm.confirmPhrase}
        busy={vm.eliteBusy}
        onCancel={() => vm.setElitePromoteConfirmOpen(false)}
        onConfirm={(phrase) => void vm.onElitePromoteModule(phrase)}
      />
      <ConfirmDialogV2 riskLevel="danger"
        open={vm.walkthroughConfirmOpen}
        title="Load demo walkthrough"
        warning="Creates sample records on this live Odoo so Operations / smart buttons are not empty."
        risks={[
          "Writes data rows on custom x_* models (named Walkthrough …)",
          "Links site, party, job, booking, and equipment lines when those models exist",
          "Reuses the first Contact / Employee / Currency if the spec points at them",
          "Try a test copy before changing production",
        ]}
        phrase={vm.confirmPhrase}
        busy={vm.busy}
        onCancel={() => vm.setWalkthroughConfirmOpen(false)}
        onConfirm={(phrase) => void vm.onSeedWalkthrough(phrase)}
      />
    </DraftStudioShell>
  );
}

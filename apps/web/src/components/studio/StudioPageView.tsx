"use client";

import { ClarifyInterstitial } from "./ClarifyInterstitial";
import { StudioBriefScreen } from "./StudioBriefScreen";
import { StudioBusyLabel } from "./StudioBusyLabel";
import { StudioConfirmDialogs } from "./StudioConfirmDialogs";
import { StudioProgress } from "./StudioProgress";
import { StudioReviewSection } from "./StudioReviewSection";
import { StudioShell } from "./StudioShell";
import { Callout } from "@/components/ui/Callout";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import { studioErrorTitle, progressLabelFromJob } from "@/lib/studio-journey";
import type { StudioPageModel } from "./use-studio-page";

export function StudioPageView(vm: StudioPageModel) {
  const error = vm.error;
  return (
    <StudioShell
      connectionId={vm.connectionId}
      journey={vm.journey}
      canvas={vm.canvas}
      hasSession={Boolean(vm.session)}
      onStartNew={vm.startOver}
    >
      {error && vm.phase !== "failed" && vm.phase !== "generating" ? (
        <Callout
          variant="danger"
          title={studioErrorTitle(vm.errorStep, error)}
          className="mb-4"
          actions={
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-testid="studio-diagnose-error"
              onClick={() => diagnoseWithExpert(error)}
            >
              Diagnose with Expert
            </Button>
          }
        >
          {error}
        </Callout>
      ) : null}

      {vm.isOdooOnline ? (
        <Callout variant="warning" title="Odoo Online connection" className="mb-4">
          Metadata apply works when RPC allows — same caps as the wizard. Custom Python
          modules and full Job Autopilot sandbox are not available on Online.
        </Callout>
      ) : null}

      {!vm.session ? (
        <StudioBriefScreen
          prompt={vm.prompt}
          busy={vm.busy !== null}
          onPromptChange={vm.setPrompt}
          onStart={() => void vm.startSession()}
          flashAstEnrich={vm.flashAstEnrich}
          flashAstEnrichHelp={vm.flashAstEnrichHelp}
          onFlashAstEnrichChange={(value) => {
            vm.setFlashAstEnrich(value);
            if (vm.connectionId?.trim()) {
              void api.patchStudioPrefs(vm.connectionId.trim(), {
                flash_ast_enrich: value,
              }).catch(() => {
                /* local toggle still applies for this session */
              });
            }
          }}
        />
      ) : null}

      {vm.session && vm.phase === "clarify" && vm.clarification ? (
        <ClarifyInterstitial
          clarification={vm.clarification}
          busy={vm.busy !== null}
          onAnswer={(mk, id, text, understanding) =>
            void vm.submitClarify(mk, id, text, understanding)
          }
        />
      ) : null}

      {vm.session && vm.phase === "generating" && !vm.error ? (
        <div className="studio-canvas-progress">
          <div className="studio-canvas-ghost" aria-hidden>
            <div className="studio-canvas-ghost-bar" />
            <div className="studio-canvas-ghost-sheet" />
          </div>
          <StudioProgress
            label={progressLabelFromJob(vm.job)}
            detail={vm.session.prompt_resolved?.slice(0, 160)}
          />
        </div>
      ) : null}

      {vm.session && (vm.phase === "failed" || (vm.phase === "generating" && vm.error)) ? (
        <Callout
          variant="danger"
          title="Generation failed"
          className="mt-6"
          actions={
            <>
              <button
                type="button"
                className="btn btn-brand btn-sm"
                disabled={vm.busy === "generate"}
                onClick={() => void vm.retryGeneration()}
              >
                {vm.busy === "generate" ? <StudioBusyLabel>Retrying…</StudioBusyLabel> : "Try again"}
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={vm.startOver}>
                Start over
              </button>
            </>
          }
        >
          {vm.job?.error || vm.error || "The draft job did not complete."}
        </Callout>
      ) : null}

      {vm.session && vm.phase === "review" ? <StudioReviewSection {...vm} /> : null}

      <StudioConfirmDialogs {...vm} />
    </StudioShell>
  );
}

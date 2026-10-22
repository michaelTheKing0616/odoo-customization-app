"use client";

import { ClarifyInterstitial } from "./ClarifyInterstitial";
import { StockAppInstallCard } from "./StockAppInstallCard";
import { StudioBriefScreen } from "./StudioBriefScreen";
import { StudioConfirmDialogs } from "./StudioConfirmDialogs";
import { StudioGeneratingCanvas, StudioGenerationFailed } from "./StudioGenerationStates";
import { StudioReviewSection } from "./StudioReviewSection";
import { StudioShell } from "./StudioShell";
import { Callout } from "@/components/ui/Callout";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import { studioErrorTitle, progressLabelFromJob } from "@/lib/studio-journey";
import type { StudioPageModel } from "./use-studio-page";
import { effectiveAiStep } from "./brief-wants-ai";

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
          Fields, views, and menus apply over RPC where Odoo Online allows it, with the same
          limits as the Worksheet. Custom Python modules and the Job Autopilot sandbox are not
          available on Online.
        </Callout>
      ) : null}

      {!vm.session ? (
        <StudioBriefScreen
          prompt={vm.prompt}
          busy={vm.busy !== null}
          onPromptChange={vm.setPrompt}
          onStart={() => void vm.startSession()}
          flashAstEnrich={effectiveAiStep(vm.flashAstEnrich, vm.prompt)}
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

      {vm.session && vm.phase === "clarify" && vm.clarification?.kind === "stock_app_install" ? (
        <StockAppInstallCard
          clarification={vm.clarification}
          onInstall={() => vm.resolveStockApp("install")}
          onDecline={() => vm.resolveStockApp("decline")}
        />
      ) : null}

      {vm.session &&
      vm.phase === "clarify" &&
      vm.clarification &&
      vm.clarification.kind !== "stock_app_install" ? (
        <ClarifyInterstitial
          clarification={vm.clarification}
          busy={vm.busy !== null}
          onAnswer={(mk, id, text, understanding) =>
            void vm.submitClarify(mk, id, text, understanding)
          }
          onRetryDesign={() => void vm.startSession()}
          onInstallApps={() => vm.installApps()}
          connectionReadOnly={vm.connection?.write_mode === "observer"}
          connectionId={vm.connectionId ?? undefined}
          isOdooOnline={vm.isOdooOnline}
          odooUrl={vm.odooUrl}
          sessionId={vm.session.id}
        />
      ) : null}

      {vm.session && vm.phase === "generating" && !vm.error ? (
        <StudioGeneratingCanvas
          runId={vm.session.job_id ?? null}
          fallbackLabel={progressLabelFromJob(vm.job)}
        />
      ) : null}

      {vm.session && (vm.phase === "failed" || (vm.phase === "generating" && vm.error)) ? (
        <StudioGenerationFailed
          message={vm.job?.error || vm.error}
          retrying={vm.busy === "generate"}
          onRetry={() => void vm.retryGeneration()}
          onStartOver={vm.startOver}
        />
      ) : null}

      {vm.session && vm.phase === "review" ? <StudioReviewSection {...vm} /> : null}

      <StudioConfirmDialogs {...vm} />
    </StudioShell>
  );
}

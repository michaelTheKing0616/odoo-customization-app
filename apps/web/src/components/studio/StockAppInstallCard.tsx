"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { DURATION, EASE_ENTER_EXIT, seconds } from "@/components/ui/motion";
import type { StudioClarification } from "@/lib/studio-session";

type StockAppInstallCardProps = {
  clarification: StudioClarification;
  /** Installs the app and resumes the request. Rejects with a one-sentence Error on failure. */
  onInstall: () => Promise<void>;
  /** Stops the request. */
  onDecline: () => Promise<void>;
};

type Phase = "idle" | "installing" | "declining";

export function StockAppInstallCard({ clarification, onInstall, onDecline }: StockAppInstallCardProps) {
  const proposal = clarification.stock_app;
  const label = proposal?.app_label || "the app";
  const installable = Boolean(proposal?.installable);
  const reduceMotion = useReducedMotion();
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);

  const enter = reduceMotion
    ? { initial: { opacity: 0 }, animate: { opacity: 1 } }
    : { initial: { opacity: 0, y: 4 }, animate: { opacity: 1, y: 0 } };
  const transition = {
    duration: seconds(reduceMotion ? DURATION.reducedMotionMs : DURATION.dropdownMs),
    ease: EASE_ENTER_EXIT.bezier,
  };

  async function install() {
    setError(null);
    setPhase("installing");
    try {
      await onInstall();
      toast.success(`${label} is installed`, { description: "Continuing your request." });
    } catch (err) {
      const message = err instanceof Error ? err.message.split("\n")[0].trim() : "";
      setError(message || `${label} could not be installed. Try again in a moment.`);
    } finally {
      setPhase("idle");
    }
  }

  async function decline() {
    setError(null);
    setPhase("declining");
    try {
      await onDecline();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Could not stop this request.");
    } finally {
      setPhase("idle");
    }
  }

  const busy = phase !== "idle";

  return (
    <motion.section
      className="card clarify-card"
      data-testid="studio-stock-app"
      aria-labelledby="studio-stock-app-question"
      aria-busy={phase === "installing"}
      initial={enter.initial}
      animate={enter.animate}
      transition={transition}
    >
      <p className="clarify-kicker">{installable ? "One app first" : "Not available here"}</p>
      <p id="studio-stock-app-question" className="clarify-question">
        {clarification.question}
      </p>
      {clarification.help ? <p className="clarify-help">{clarification.help}</p> : null}

      <p className="clarify-help" aria-live="polite" data-testid="studio-stock-app-status">
        {phase === "installing"
          ? `Installing ${label}. This can take a minute. Keep this tab open.`
          : ""}
      </p>

      <AnimatePresence initial={false}>
        {error ? (
          <motion.div
            key="error"
            role="alert"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={transition}
          >
            <Callout
              variant="danger"
              title={`${label} was not installed`}
              className="mt-3"
              testId="studio-stock-app-error"
            >
              {error}
            </Callout>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="studio-chip-row" style={{ marginTop: 16 }}>
        {installable ? (
          <Button
            type="button"
            variant="primary"
            size="sm"
            loading={phase === "installing"}
            disabled={busy}
            data-testid="studio-stock-app-install"
            onClick={() => void install()}
          >
            {phase === "installing"
              ? `Installing ${label}…`
              : error
                ? `Try installing ${label} again`
                : proposal?.install_label || `Install ${label} and continue`}
          </Button>
        ) : null}
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={busy}
          data-testid="studio-stock-app-decline"
          onClick={() => void decline()}
        >
          {proposal?.decline_label || "Not now"}
        </Button>
      </div>
    </motion.section>
  );
}

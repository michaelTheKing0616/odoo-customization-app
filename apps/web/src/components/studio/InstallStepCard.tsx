"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { DURATION, EASE_ENTER_EXIT, seconds } from "@/components/ui/motion";
import type { StudioInstallStep } from "@/lib/studio-session";

type InstallStepCardProps = {
  step: StudioInstallStep;
  /** Installs the listed apps and re-checks the database. Rejects with a one-sentence Error. */
  onInstall?: () => Promise<void>;
  busy?: boolean;
  /** The connection is read-only. Install stays disabled and the guidance shows up front. */
  readOnly?: boolean;
};

const READ_ONLY_HELP =
  "This connection is read-only, so App Studio can't install apps on it. Switch the connection to Standard in Connections, then come back and install.";

/** S11: the install step between the diagnosis and the build. Same pattern as StockAppInstallCard. */
export function InstallStepCard({
  step,
  onInstall,
  busy,
  readOnly,
}: InstallStepCardProps) {
  const reduceMotion = useReducedMotion();
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const names = step.apps.map((a) => a.label).join(", ");
  const locked = Boolean(readOnly || step.read_only);
  const refresh = Boolean(step.refresh);

  const enter = reduceMotion
    ? { initial: { opacity: 0 }, animate: { opacity: 1 } }
    : { initial: { opacity: 0, y: 4 }, animate: { opacity: 1, y: 0 } };
  const transition = {
    duration: seconds(
      reduceMotion ? DURATION.reducedMotionMs : DURATION.dropdownMs,
    ),
    ease: EASE_ENTER_EXIT.bezier,
  };

  async function install() {
    if (!onInstall || locked) return;
    setError(null);
    setInstalling(true);
    try {
      await onInstall();
      toast.success(
        refresh
          ? "Design updated"
          : `${names} ${step.apps.length === 1 ? "is" : "are"} ready`,
        { description: "Check the design, then build." },
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message.split("\n")[0].trim() : "";
      setError(
        message ||
          (refresh
            ? "The design could not be updated. Try again in a moment."
            : `${names} could not be installed. Try again in a moment.`),
      );
    } finally {
      setInstalling(false);
    }
  }

  return (
    <motion.section
      className="card clarify-card"
      data-testid="studio-install-step"
      aria-labelledby="studio-install-step-title"
      aria-busy={installing}
      initial={enter.initial}
      animate={enter.animate}
      transition={transition}
      style={{ marginTop: 16 }}
    >
      <p className="clarify-kicker">Before you build</p>
      <h3 id="studio-install-step-title" className="clarify-question">
        {step.title}
      </h3>
      <p className="clarify-help">{step.message}</p>
      {locked ? (
        <Callout
          variant="warning"
          title="This connection is read-only"
          className="mt-3"
          testId="studio-install-step-readonly"
        >
          <span id="studio-install-step-readonly-help">
            {step.read_only_message || READ_ONLY_HELP}
          </span>
        </Callout>
      ) : null}
      <ul className="diagnosis-facts" data-testid="studio-install-step-apps">
        {step.apps.map((app) => (
          <li key={app.module} className="diagnosis-constraint-row">
            <span>
              <strong>{app.label}</strong>
              <span className="clarify-help diagnosis-row-help">
                {" "}
                {app.why}
              </span>
            </span>
          </li>
        ))}
      </ul>

      <p
        className="clarify-help"
        aria-live="polite"
        data-testid="studio-install-step-status"
      >
        {installing
          ? refresh
            ? "Updating the design to use the installed apps."
            : step.can_install
              ? `Installing ${names}. This can take a minute. Keep this tab open.`
              : `Checking your database for ${names}.`
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
              variant={step.can_install ? "danger" : "warning"}
              title={refresh ? "Design not updated" : `${names} not installed`}
              className="mt-3"
              testId="studio-install-step-error"
            >
              {error}
            </Callout>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {onInstall ? (
        <div className="studio-chip-row" style={{ marginTop: 16 }}>
          <Button
            type="button"
            variant={step.can_install || locked ? "primary" : "secondary"}
            size="sm"
            loading={installing}
            disabled={installing || busy || locked}
            aria-describedby={locked ? "studio-install-step-readonly-help" : undefined}
            data-testid="studio-install-step-install"
            onClick={() => void install()}
          >
            {installing
              ? refresh
                ? "Updating…"
                : step.can_install
                  ? `Installing ${names}…`
                  : "Checking…"
              : error
                ? step.can_install
                  ? "Try again"
                  : "Check again"
                : step.install_label}
          </Button>
        </div>
      ) : null}
    </motion.section>
  );
}

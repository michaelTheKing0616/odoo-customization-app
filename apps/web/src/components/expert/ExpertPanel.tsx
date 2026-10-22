"use client";

import { usePathname } from "next/navigation";
import { SheetMotion } from "@/components/ui/motion/SheetMotion";
import { useShell } from "@/context/ShellContext";
import { EXPERT_HONESTY_LINE, isExpertDestinationPath } from "@/lib/expert-journey";
import { useExpertConversation, type ExpertSurface } from "@/lib/use-expert-conversation";
import { ExpertClearDialog, ExpertConversation } from "./ExpertConversation";
import { ExpertHeader } from "./ExpertHeader";
import "@/styles/studio-refinement.css";

type ExpertPanelProps = {
  /** `drawer` (default, mounted by AppShell) or `page` (inline on /connections/[id]/expert). */
  variant?: ExpertSurface;
};

/**
 * Odoo Expert. One component for both surfaces (UI-S-25 must-not: drawer and page never diverge).
 * On the Expert destination route the shell drawer stands down, so there is only ever one live
 * conversation instance and one consumer of `openExpert` prefills.
 */
export function ExpertPanel({ variant = "drawer" }: ExpertPanelProps) {
  const pathname = usePathname();
  if (variant === "page") return <ExpertPageSurface />;
  if (isExpertDestinationPath(pathname)) return null;
  return <ExpertDrawer />;
}

function ExpertDrawer() {
  const { expertOpen, setExpertOpen } = useShell();
  const state = useExpertConversation("drawer");
  return (
    <>
      <SheetMotion
        open={expertOpen}
        onOpenChange={setExpertOpen}
        title="Odoo Expert"
        description={EXPERT_HONESTY_LINE}
        testId="expert-panel"
        className="studio-refinement expert-drawer max-w-xl"
        header={<ExpertHeader />}
      >
        <ExpertConversation state={state} />
      </SheetMotion>
      <ExpertClearDialog state={state} />
    </>
  );
}

function ExpertPageSurface() {
  const state = useExpertConversation("page");
  return (
    <>
      <div className="expert-page-surface" data-testid="expert-page-surface">
        <ExpertConversation state={state} />
      </div>
      <ExpertClearDialog state={state} />
    </>
  );
}

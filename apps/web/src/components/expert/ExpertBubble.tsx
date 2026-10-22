"use client";

import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { IconExpert } from "@/components/ui/icons";
import { Tooltip } from "@/components/ui/Tooltip";
import { useShell } from "@/context/ShellContext";
import { cn } from "@/lib/cn";
import { isExpertDestinationPath } from "@/lib/expert-journey";

/** The two prompts every page gets; anything else is specific to this page or model. */
const GENERIC_PROMPT_IDS = new Set(["modules", "security"]);

/** Touch 110: true only when Expert has a prompt specific to this page (not the generic pair). */
export function hasPageTip(prompts: { id: string }[] | undefined): boolean {
  return Boolean(prompts?.some((p) => !GENERIC_PROMPT_IDS.has(p.id)));
}

type Props = {
  className?: string;
};

export function ExpertBubble({ className }: Props) {
  const { expertOpen, openExpert, uiContext } = useShell();
  const pathname = usePathname();
  const tips = useQuery({
    queryKey: ["expert-page-tip", pathname, uiContext.model],
    queryFn: () => api.expertSuggestedPrompts({ route: pathname, model: uiContext.model }),
    enabled: !expertOpen,
    staleTime: 5 * 60_000,
    retry: false,
  });
  const tip = hasPageTip(tips.data);

  // On the Expert page the conversation is already on screen; a launcher would open a duplicate.
  if (expertOpen || isExpertDestinationPath(pathname)) return null;

  return (
    <div
      className={cn(
        "pointer-events-none fixed bottom-6 right-6 z-[70] flex flex-col items-end gap-2",
        className,
      )}
    >
      <p className="expert-launcher-hint pointer-events-none hidden sm:block" aria-hidden>
        Odoo Expert
      </p>
      <Tooltip label="Open Odoo Expert. Grounded answers, never auto-promotes.">
        <button
          type="button"
          data-testid="open-expert"
          aria-label={tip ? "Open Odoo Expert (has a tip for this page)" : "Open Odoo Expert"}
          onClick={() => openExpert()}
          className={cn(
            "expert-launcher pointer-events-auto group relative flex h-12 w-12 items-center justify-center rounded-full",
            "bg-accent text-on-accent shadow-lg",
            "ring-4 ring-accent/10 transition-transform duration-200 hover:scale-[1.04] hover:bg-accent-hover hover:shadow-xl",
            "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/40",
          )}
        >
          <IconExpert className="relative h-5 w-5 transition-transform group-hover:scale-110" />
          {tip ? <span className="expert-tip-dot" data-testid="expert-tip-dot" aria-hidden /> : null}
        </button>
      </Tooltip>
    </div>
  );
}

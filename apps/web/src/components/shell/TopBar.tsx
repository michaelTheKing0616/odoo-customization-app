"use client";

import { BackgroundWorkPill, Keycap } from "@/components/ui/craft";
import Link from "next/link";
import { InstanceIdentity } from "@/components/shell/InstanceIdentity";
import { Button } from "@/components/ui/Button";
import { Breadcrumbs } from "@/components/ui/layout-primitives";
import { Command, IconExpert, Moon, Sun } from "@/components/ui/icons";
import { useTheme } from "@/components/theme/ThemeProvider";
import { useShell } from "@/context/ShellContext";
import { breadcrumbForPath } from "@/lib/nav";
import { Tooltip } from "@/components/ui/Tooltip";
import { WriteModeBadge } from "@/components/shell/WriteModeBadge";
import { AnomalyBanner } from "@/components/shell/AnomalyBanner";
import { WorkspacePlanBadge } from "@/components/billing/WorkspacePlanBadge";
import type { Connection } from "@/lib/api";

type Props = {
  connection: Connection;
  /** Unused since the switcher moved to the sidebar; kept so callers need no change. */
  connections?: Connection[];
  pathname: string;
};

export function TopBar({ connection, pathname }: Props) {
  const { toggle, resolved } = useTheme();
  const { setCommandOpen, setExpertOpen } = useShell();
  const crumbs = breadcrumbForPath(connection.id, pathname);

  return (
    <header className="border-b border-border-subtle bg-surface-raised" data-testid="app-topbar">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <div className="min-w-0 flex-1">
          {/* Switching connections lives in the sidebar header (ConnectionSwitcher) and Cmd-K. */}
          <InstanceIdentity connection={connection} className="mt-2" />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <WriteModeBadge mode={connection.write_mode ?? "standard"} />
            <WorkspacePlanBadge />
          </div>
          <AnomalyBanner connection={connection} />
        </div>
        <div className="flex items-center gap-2">
          <BackgroundWorkPill />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCommandOpen(true)}
            data-testid="open-command-palette"
            data-shortcut="⌘K"
            aria-label="Open command palette"
          >
            <Command className="h-4 w-4" />
            <span className="hidden sm:inline">Command</span>
            <Keycap keys="Mod+K" />
          </Button>
          <Tooltip label="Odoo Expert — grounded answers, never auto-promotes">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExpertOpen(true)}
              data-testid="topbar-open-expert"
              aria-label="Open Odoo Expert"
            >
              <IconExpert className="h-4 w-4" />
              <span className="hidden sm:inline">Expert</span>
            </Button>
          </Tooltip>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggle}
            aria-label="Toggle theme"
            data-testid="theme-toggle"
          >
            {resolved === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <Link href="/settings" className="text-ui-body text-muted hover:text-ink">
            Settings
          </Link>
        </div>
      </div>
      <div className="border-t border-border-subtle px-4 py-2">
        <Breadcrumbs items={crumbs} />
      </div>
    </header>
  );
}

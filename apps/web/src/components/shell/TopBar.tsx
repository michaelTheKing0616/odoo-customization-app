"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { InstanceIdentity } from "@/components/shell/InstanceIdentity";
import { Button } from "@/components/ui/Button";
import { Breadcrumbs } from "@/components/ui/layout-primitives";
import { Command, IconExpert, Moon, Sun } from "@/components/ui/icons";
import { Kbd } from "@/components/ui/layout-primitives";
import { useTheme } from "@/components/theme/ThemeProvider";
import { useShell } from "@/context/ShellContext";
import { breadcrumbForPath } from "@/lib/nav";
import { WriteModeBadge } from "@/components/shell/WriteModeBadge";
import { AnomalyBanner } from "@/components/shell/AnomalyBanner";
import { WorkspacePlanBadge } from "@/components/billing/WorkspacePlanBadge";
import type { Connection } from "@/lib/api";

type Props = {
  connection: Connection;
  connections: Connection[];
  pathname: string;
};

export function TopBar({ connection, connections, pathname }: Props) {
  const router = useRouter();
  const { toggle, resolved } = useTheme();
  const { setCommandOpen, setExpertOpen } = useShell();
  const crumbs = breadcrumbForPath(connection.id, pathname);

  return (
    <header className="border-b border-border-subtle bg-surface-raised" data-testid="app-topbar">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <div className="min-w-0 flex-1">
          <label className="sr-only" htmlFor="connection-switcher">
            Switch connection
          </label>
          <select
            id="connection-switcher"
            className="max-w-xs rounded-md border border-border-subtle bg-surface px-2 py-1.5 text-sm"
            value={connection.id}
            onChange={(e) => router.push(`/connections/${e.target.value}`)}
            data-testid="connection-switcher"
          >
            {connections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <InstanceIdentity connection={connection} className="mt-2" />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <WriteModeBadge mode={connection.write_mode ?? "standard"} />
            <WorkspacePlanBadge />
          </div>
          <AnomalyBanner connection={connection} />
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCommandOpen(true)}
            data-testid="open-command-palette"
            aria-label="Open command palette"
          >
            <Command className="h-4 w-4" />
            <span className="hidden sm:inline">Command</span>
            <Kbd>⌘K</Kbd>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpertOpen(true)}
            data-testid="open-expert"
            aria-label="Open Odoo Expert"
          >
            <IconExpert className="h-4 w-4" />
            <span className="hidden sm:inline">Expert</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggle}
            aria-label="Toggle theme"
            data-testid="theme-toggle"
          >
            {resolved === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <Link href="/settings" className="text-sm text-muted hover:text-ink">
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

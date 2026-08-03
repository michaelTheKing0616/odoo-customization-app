"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ChevronDown, ChevronRight, Menu } from "@/components/ui/icons";
import { Tooltip } from "@/components/ui/Tooltip";
import { useShell } from "@/context/ShellContext";
import {
  NAV_GROUPS,
  NAV_ITEMS,
  navItemLocked,
  type NavItem,
} from "@/lib/nav";
import { cn } from "@/lib/cn";
import type { Connection } from "@/lib/api";

type Props = {
  connection: Connection;
};

export function Sidebar({ connection }: Props) {
  const pathname = usePathname();
  const { sidebarCollapsed, setSidebarCollapsed } = useShell();
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(NAV_GROUPS.map((g) => [g.id, true])),
  );
  const [lockedItem, setLockedItem] = useState<NavItem | null>(null);
  const supported = connection.capabilities?.supported ?? [];
  const installedModules = connection.capabilities?.installed_modules_sample ?? [];

  return (
    <>
      <aside
        data-testid="app-sidebar"
        className={cn(
          "flex h-full shrink-0 flex-col border-r border-border-subtle bg-surface-raised",
          sidebarCollapsed ? "w-14" : "w-60",
        )}
      >
        <div className="flex items-center justify-between border-b border-border-subtle px-3 py-3">
          {!sidebarCollapsed ? (
            <span className="text-sm font-semibold text-ink truncate">{connection.name}</span>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          >
            <Menu className="h-4 w-4" />
          </Button>
        </div>
        <nav className="flex-1 overflow-y-auto p-2">
          {NAV_GROUPS.map((group) => {
            const items = NAV_ITEMS.filter(
              (item) => item.group === group.id && item.shipped !== false,
            );
            if (!items.length) return null;
            const isOpen = expanded[group.id] ?? true;
            return (
              <div key={group.id} className="mb-2">
                {!sidebarCollapsed ? (
                  <button
                    type="button"
                    className="flex w-full items-center gap-1 px-2 py-1 text-xs font-medium uppercase tracking-wide text-muted"
                    onClick={() =>
                      setExpanded((prev) => ({ ...prev, [group.id]: !isOpen }))
                    }
                  >
                    {isOpen ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                    {group.label}
                  </button>
                ) : null}
                {(sidebarCollapsed || isOpen) &&
                  items.map((item) => {
                    const href = item.href(connection.id);
                    const active = pathname === href || pathname.startsWith(`${href}/`);
                    const locked = navItemLocked(item, supported, installedModules);
                    const Icon = item.icon;
                    const link = (
                      <Link
                        href={locked ? "#" : href}
                        onClick={(e) => {
                          if (locked) {
                            e.preventDefault();
                            setLockedItem(item);
                          }
                        }}
                        className={cn(
                          "flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
                          active
                            ? "bg-accent-subtle text-accent font-medium"
                            : "text-ink hover:bg-surface-muted",
                          sidebarCollapsed && "justify-center px-0",
                        )}
                        data-testid={`nav-${item.id}`}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        {!sidebarCollapsed ? (
                          <>
                            <span className="truncate">{item.label}</span>
                            {locked ? <Badge variant="lock">Locked</Badge> : null}
                          </>
                        ) : null}
                      </Link>
                    );
                    return (
                      <div key={item.id} className="mb-0.5">
                        {sidebarCollapsed ? (
                          <Tooltip label={item.label}>{link}</Tooltip>
                        ) : (
                          link
                        )}
                      </div>
                    );
                  })}
              </div>
            );
          })}
        </nav>
      </aside>
      {lockedItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-w-lg w-full">
            <Callout
              variant="warning"
              title={lockedItem.gatingTitle ?? "Feature not available"}
              testId="nav-gating-callout"
            >
              <p>{lockedItem.gatingWhy}</p>
              {lockedItem.gatingOptions ? (
                <ul className="mt-2 list-disc pl-5">
                  {lockedItem.gatingOptions.map((opt) => (
                    <li key={opt}>{opt}</li>
                  ))}
                </ul>
              ) : null}
            </Callout>
            <Button className="mt-3" variant="secondary" onClick={() => setLockedItem(null)}>
              Close
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}

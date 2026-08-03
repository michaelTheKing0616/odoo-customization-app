"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExpertPanel } from "@/components/expert/ExpertPanel";
import { Callout } from "@/components/ui/Callout";
import { CommandPalette, type CommandItem } from "@/components/ui/CommandPalette";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";
import { ExpertDiagnoseListener } from "@/lib/expert-diagnostics";
import { useShell } from "@/context/ShellContext";
import { api } from "@/lib/api";
import { NAV_ITEMS } from "@/lib/nav";

type Props = {
  connectionId: string;
  children: React.ReactNode;
};

export function AppShell({ connectionId, children }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    commandOpen,
    setCommandOpen,
    setExpertOpen,
    setUiContext,
  } = useShell();

  const connectionQuery = useQuery({
    queryKey: ["connection", connectionId],
    queryFn: () => api.getConnection(connectionId),
  });

  const connectionsQuery = useQuery({
    queryKey: ["connections"],
    queryFn: () => api.listConnections(),
  });

  const modelsQuery = useQuery({
    queryKey: ["models", connectionId],
    queryFn: () => api.listModels(connectionId, true),
    enabled: commandOpen,
  });

  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const update = () => setOffline(typeof navigator !== "undefined" && !navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  useEffect(() => {
    setUiContext({ route: pathname });
  }, [pathname, setUiContext]);

  useEffect(() => {
    if (searchParams.get("expert") === "1") {
      setExpertOpen(true);
    }
  }, [searchParams, setExpertOpen]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setCommandOpen]);

  const commandItems = useMemo(() => {
    const items: CommandItem[] = NAV_ITEMS.filter((n) => n.shipped !== false).map((n) => ({
      id: n.id,
      label: n.label,
      group: "Navigate",
      keywords: [n.group],
      onSelect: () => router.push(n.href(connectionId)),
    }));
    for (const model of modelsQuery.data ?? []) {
      items.push({
        id: `model-${model.model}`,
        label: `Model: ${model.model}`,
        group: "Jump to model",
        keywords: [model.name ?? ""],
        onSelect: () =>
          router.push(`/connections/${connectionId}/builder?model=${encodeURIComponent(model.model)}`),
      });
    }
    return items;
  }, [connectionId, modelsQuery.data, router]);

  const connection = connectionQuery.data;
  const connections = connectionsQuery.data ?? [];

  if (connectionQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        Loading connection…
      </div>
    );
  }

  if (connectionQuery.isError || !connection) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Callout variant="danger" title="Could not load connection">
          Check the API is running and this connection still exists.
        </Callout>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-surface" data-testid="app-shell">
      <Sidebar connection={connection} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar connection={connection} connections={connections} pathname={pathname} />
        {offline ? (
          <div className="border-b border-warning/30 bg-warning-subtle px-4 py-2 text-sm text-warning">
            You appear to be offline. Changes that need Odoo will fail until connectivity returns.
          </div>
        ) : null}
        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      </div>
      <ExpertPanel />
      <ExpertDiagnoseListener />
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} items={commandItems} />
    </div>
  );
}

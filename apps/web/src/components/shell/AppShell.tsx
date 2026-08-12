"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { ExpertPanel } from "@/components/expert/ExpertPanel";
import { ExpertBubble } from "@/components/expert/ExpertBubble";
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
    openExpert,
    setUiContext,
    uiContext,
  } = useShell();

  const [commandSearch, setCommandSearch] = useState("");

  const connectionQuery = useQuery({
    queryKey: ["connection", connectionId],
    queryFn: () => api.getConnection(connectionId),
    enabled: Boolean(connectionId),
    retry: false,
    refetchOnWindowFocus: false,
  });

  const connectionsQuery = useQuery({
    queryKey: ["connections"],
    queryFn: () => api.listConnections(),
    retry: false,
    refetchOnWindowFocus: false,
  });

  const [slowLoad, setSlowLoad] = useState(false);
  useEffect(() => {
    if (!connectionQuery.isPending) {
      setSlowLoad(false);
      return;
    }
    const t = window.setTimeout(() => setSlowLoad(true), 3_000);
    return () => window.clearTimeout(t);
  }, [connectionQuery.isPending]);

  const modelsQuery = useQuery({
    queryKey: ["models", connectionId],
    queryFn: () => api.listModels(connectionId, true),
    enabled: commandOpen,
  });

  const suggestedPromptsQuery = useQuery({
    queryKey: ["expert-suggested-prompts", pathname, uiContext.model],
    queryFn: () =>
      api.expertSuggestedPrompts({
        route: pathname,
        model: uiContext.model,
        view_type: uiContext.viewType,
        draft_summary: uiContext.draftSummary,
      }),
    enabled: commandOpen,
    staleTime: 60_000,
  });

  const nlSearchQuery = useQuery({
    queryKey: ["expert-nl-search", connectionId, commandSearch],
    queryFn: () => api.expertNLSearch({ query: commandSearch, connection_id: connectionId }),
    enabled: commandOpen && commandSearch.trim().length >= 4,
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
    const resIdRaw = searchParams.get("res_id");
    const model = searchParams.get("model");
    if (resIdRaw || model) {
      setUiContext({
        ...(model ? { model } : {}),
        ...(resIdRaw ? { resId: Number.parseInt(resIdRaw, 10) } : {}),
      });
    }
  }, [searchParams, setExpertOpen, setUiContext]);

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
    items.push({
      id: "open-expert",
      label: "Open Odoo Expert",
      group: "Expert",
      keywords: ["ask", "help", "ai"],
      onSelect: () => openExpert(),
    });
    for (const prompt of suggestedPromptsQuery.data ?? []) {
      items.push({
        id: `expert-prompt-${prompt.id}`,
        label: prompt.label,
        group: "Expert prompts",
        keywords: [prompt.question],
        onSelect: () => openExpert({ question: prompt.question, autoSubmit: true, freshThread: true }),
      });
    }
    return items;
  }, [connectionId, modelsQuery.data, openExpert, router, suggestedPromptsQuery.data]);

  const dynamicCommandItems = useMemo(() => {
    const hits = nlSearchQuery.data?.hits ?? [];
    return hits.map((hit) => ({
      id: hit.id,
      label: hit.label,
      group: hit.kind === "expert" ? "Expert search" : "Search",
      keywords: [hit.description, hit.expert_question ?? ""],
      onSelect: () => {
        if (hit.href) {
          router.push(hit.href);
          return;
        }
        if (hit.expert_question) {
          openExpert({ question: hit.expert_question, autoSubmit: true, freshThread: true });
        }
      },
    }));
  }, [nlSearchQuery.data, openExpert, router]);

  const connection = connectionQuery.data;
  const connections = connectionsQuery.data ?? [];

  if (!connectionId) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Callout variant="danger" title="Invalid connection URL">
          Open a connection from the home page or pick one from your saved connections list.
        </Callout>
      </div>
    );
  }

  if (connectionQuery.isPending) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-muted">
        <p>Loading connection…</p>
        {slowLoad ? (
          <p className="max-w-md text-center text-sm">
            Still waiting — check the API is running on port 8001{" "}
            <code className="text-xs">(uv run uvicorn app.main:app --port 8001)</code>.
          </p>
        ) : null}
      </div>
    );
  }

  if (connectionQuery.isError || !connection) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Callout variant="danger" title="Could not load connection">
          <p className="text-sm">
            {connectionQuery.error instanceof Error
              ? connectionQuery.error.message
              : "Check the API is running and this connection still exists."}
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => void connectionQuery.refetch()}
          >
            Retry
          </Button>
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
      <ExpertBubble />
      <ExpertDiagnoseListener />
      <CommandPalette
        open={commandOpen}
        onOpenChange={(open) => {
          setCommandOpen(open);
          if (!open) setCommandSearch("");
        }}
        items={commandItems}
        dynamicItems={dynamicCommandItems}
        onSearchChange={setCommandSearch}
      />
    </div>
  );
}

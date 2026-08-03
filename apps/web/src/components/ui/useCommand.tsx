"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { CommandItem } from "@/components/ui/CommandPalette";

type CommandRegistration = {
  group: string;
  items: Omit<CommandItem, "group">[];
};

type CommandRegistryContextValue = {
  register: (registration: CommandRegistration) => () => void;
  items: CommandItem[];
};

const CommandRegistryContext = createContext<CommandRegistryContextValue | null>(null);

export function CommandRegistryProvider({ children }: { children: React.ReactNode }) {
  const [registrations, setRegistrations] = useState<CommandRegistration[]>([]);

  const register = useCallback((registration: CommandRegistration) => {
    setRegistrations((prev) => [...prev, registration]);
    return () => {
      setRegistrations((prev) => prev.filter((r) => r !== registration));
    };
  }, []);

  const items = useMemo(
    () =>
      registrations.flatMap((r) =>
        r.items.map((item) => ({ ...item, group: r.group })),
      ),
    [registrations],
  );

  const value = useMemo(() => ({ register, items }), [register, items]);

  return (
    <CommandRegistryContext.Provider value={value}>
      {children}
    </CommandRegistryContext.Provider>
  );
}

export function useCommand(group: string, items: Omit<CommandItem, "group">[]) {
  const ctx = useContext(CommandRegistryContext);
  const serialized = JSON.stringify(items);

  useEffect(() => {
    if (!ctx) return;
    const parsed = JSON.parse(serialized) as Omit<CommandItem, "group">[];
    return ctx.register({ group, items: parsed });
  }, [ctx, group, serialized]);
}

export function useRegisteredCommands() {
  const ctx = useContext(CommandRegistryContext);
  return ctx?.items ?? [];
}

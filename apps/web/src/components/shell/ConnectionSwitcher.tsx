"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { ChevronDown } from "@/components/ui/icons";
import { isTestCopy } from "@/components/ui/craft";
import type { Connection } from "@/lib/api";

type Row = Pick<Connection, "id" | "name"> & Partial<Connection>;

/** "Live" or "Test", plus the Odoo version when known: what you need to tell databases apart. */
export function connectionTag(c: Row): string {
  const kind = isTestCopy(c) ? "Test" : "Live";
  return c.server_version ? `${kind} · Odoo ${String(c.server_version).split(".")[0]}` : kind;
}

/**
 * Sidebar header: the current connection's name opens a menu of saved connections,
 * then "All connections" (the Connect page) and "Add connection". Arrow keys, Home/End, Enter, Escape.
 */
export function ConnectionSwitcher({ current, connections }: { current: Row; connections: Row[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const id = useId();
  // Keep the menu short: the current connection plus up to 7 others; "All connections" shows the rest.
  const others = connections.length ? [current, ...connections.filter((c) => c.id !== current.id).slice(0, 7)] : [current];
  const entries: { key: string; label: string; detail?: string; current?: boolean; go: () => void }[] = [
    ...others.map((c) => ({ key: c.id, label: c.name, detail: connectionTag(c), current: c.id === current.id, go: () => { if (c.id !== current.id) router.push(`/connections/${c.id}`); } })),
    { key: "all", label: "All connections", go: () => router.push("/connect") },
    { key: "add", label: "Add connection", go: () => router.push("/connect#new") },
  ];
  const items = () => Array.from(menu.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);

  useEffect(() => {
    if (!open) return;
    const first = items().find((el) => el.getAttribute("aria-current") === "true") ?? items()[0];
    first?.focus();
    const away = (e: PointerEvent) => {
      if (!menu.current?.contains(e.target as Node) && !btn.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", away, true);
    return () => window.removeEventListener("pointerdown", away, true);
  }, [open]);

  const close = (refocus = true) => { setOpen(false); if (refocus) btn.current?.focus(); };
  const onMenuKey = (e: KeyboardEvent) => {
    const list = items();
    const i = list.indexOf(document.activeElement as HTMLElement);
    const to = (n: number) => { e.preventDefault(); list[(n + list.length) % list.length]?.focus(); };
    if (e.key === "ArrowDown") to(i + 1);
    else if (e.key === "ArrowUp") to(i - 1);
    else if (e.key === "Home") to(0);
    else if (e.key === "End") to(list.length - 1);
    else if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "Tab") close(false);
  };

  return (
    <div className="relative min-w-0">
      <button
        ref={btn}
        type="button"
        className="flex w-full min-w-0 items-center gap-1 rounded-md px-1 py-0.5 text-left text-[11px] text-muted hover:bg-surface-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-label={`Connection: ${current.name} (${connectionTag(current)}). Switch connection`}
        data-testid="sidebar-switcher"
        title={current.name}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => { if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setOpen(true); } }}
      >
        <span className="truncate">{current.name}</span>
        <ChevronDown className="h-3 w-3 shrink-0" aria-hidden />
      </button>
      {open ? (
        <div
          ref={menu}
          id={id}
          role="menu"
          aria-label="Switch connection"
          data-testid="sidebar-switcher-menu"
          onKeyDown={onMenuKey}
          className="absolute left-0 top-full z-50 mt-1 w-64 rounded-md border border-border-subtle bg-surface-raised p-1 text-sm shadow-lg"
        >
          {entries.map((x, n) => (
            <div key={x.key}>
              {x.key === "all" ? <div role="separator" className="my-1 h-px bg-border-subtle" /> : null}
              <button
                type="button"
                role="menuitem"
                tabIndex={-1}
                aria-current={x.current ? "true" : undefined}
                data-testid={`sidebar-switcher-${x.key}`}
                className="flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-ink hover:bg-surface-muted focus:bg-surface-muted focus:outline-none"
                onClick={() => { close(false); x.go(); }}
              >
                <span className="truncate">{x.label}{x.current ? <span className="sr-only"> (current)</span> : null}</span>
                {x.detail ? <span className="shrink-0 text-xs text-muted">{x.detail}</span> : null}
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

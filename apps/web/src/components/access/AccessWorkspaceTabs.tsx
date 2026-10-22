"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { ACCESS_TAB_LABELS, type AccessTab } from "@/lib/accessScreen";

type AccessWorkspaceTabsProps = {
  tabs: AccessTab[];
  value: AccessTab;
  onChange: (tab: AccessTab) => void;
  counts?: Partial<Record<AccessTab, number>>;
  /** Right-aligned toolbar content (e.g. the model picker). */
  aside?: ReactNode;
  children: ReactNode;
};

/** Segmented tablist. Arrow keys move and select (automatic activation). */
export function AccessWorkspaceTabs({
  tabs,
  value,
  onChange,
  counts,
  aside,
  children,
}: AccessWorkspaceTabsProps) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const active = tabs.includes(value) ? value : tabs[0];

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const idx = tabs.indexOf(active);
    let next = idx;
    if (event.key === "ArrowRight") next = (idx + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    else return;
    event.preventDefault();
    onChange(tabs[next]);
    listRef.current?.querySelector<HTMLButtonElement>(`#access-tab-${tabs[next]}`)?.focus();
  }

  return (
    <div
      className="mt-8 grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4"
      data-testid="access-workspace"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div
          ref={listRef}
          role="tablist"
          aria-label="Access workspace"
          className="ax-tabs"
          onKeyDown={onKeyDown}
          data-testid="access-tabs"
        >
          {tabs.map((tab) => {
            const selected = tab === active;
            const count = counts?.[tab];
            return (
              <button
                key={tab}
                id={`access-tab-${tab}`}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls={`access-panel-${tab}`}
                tabIndex={selected ? 0 : -1}
                className="ax-tab"
                onClick={() => onChange(tab)}
                data-testid={`access-tab-${tab}`}
              >
                {ACCESS_TAB_LABELS[tab]}
                {typeof count === "number" ? <span className="ax-tab-count">{count}</span> : null}
              </button>
            );
          })}
        </div>
        {aside}
      </div>
      <div
        role="tabpanel"
        id={`access-panel-${active}`}
        aria-labelledby={`access-tab-${active}`}
        className="min-w-0"
        data-testid={`access-panel-${active}`}
      >
        {children}
      </div>
    </div>
  );
}

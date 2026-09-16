"use client";

import type { ReactNode } from "react";

export type ListComposerShellProps = {
  list: ReactNode;
  detail: ReactNode;
  className?: string;
  /** When true, detail pane plays enter motion (list→composer). */
  animateDetail?: boolean;
};

/**
 * Shared list → composer layout (Automations / Menus / Access / Builder).
 * Left list + right composer/detail; detail enters with quiet 180ms motion.
 */
export function ListComposerShell({
  list,
  detail,
  className = "",
  animateDetail = true,
}: ListComposerShellProps) {
  return (
    <div
      className={`list-composer-shell mt-6 grid gap-6 lg:grid-cols-[minmax(240px,320px)_minmax(0,1fr)] ${className}`.trim()}
      data-testid="list-composer-shell"
    >
      <div className="list-composer-list" data-testid="list-composer-list">
        {list}
      </div>
      <div
        className={
          animateDetail
            ? "list-composer-pane space-y-4"
            : "list-composer-pane list-composer-pane--static space-y-4"
        }
        data-testid="list-composer-pane"
      >
        {detail}
      </div>
    </div>
  );
}

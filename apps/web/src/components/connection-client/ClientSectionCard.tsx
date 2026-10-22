"use client";

import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";

export type ClientSectionState<T> =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: T };

type ClientSectionCardProps<T> = {
  testId: string;
  title: string;
  description: string;
  state: ClientSectionState<T>;
  onRetry: () => void;
  renderReady: (data: T) => React.ReactNode;
  renderEmpty?: () => React.ReactNode;
  isEmpty?: (data: T) => boolean;
};

export function ClientSectionCard<T>({
  testId,
  title,
  description,
  state,
  onRetry,
  renderReady,
  renderEmpty,
  isEmpty,
}: ClientSectionCardProps<T>) {
  return (
    <Card className="flex flex-col p-4" data-testid={testId}>
      <header className="mb-3">
        <h2 className="text-sm font-medium text-ink">{title}</h2>
        <p className="mt-0.5 text-xs text-muted">{description}</p>
      </header>
      <div className="min-h-[4.5rem] flex-1" aria-live="polite">
        {state.phase === "loading" ? (
          <div className="space-y-2" data-testid={`${testId}-loading`}>
            <Skeleton className="h-4 w-full max-w-md" />
            <Skeleton className="h-4 w-48" />
          </div>
        ) : null}
        {state.phase === "error" ? (
          <div className="space-y-2" data-testid={`${testId}-error`}>
            <p className="text-sm text-ink" role="alert">
              {state.message}
            </p>
            <Button type="button" variant="secondary" size="sm" onClick={onRetry}>
              Retry
            </Button>
          </div>
        ) : null}
        {state.phase === "ready" && isEmpty?.(state.data) ? (
          renderEmpty?.() ?? (
            <EmptyState
              title="Nothing here yet"
              description="This section will populate when data is available for this connection."
            />
          )
        ) : null}
        {state.phase === "ready" && !(isEmpty?.(state.data) ?? false)
          ? renderReady(state.data)
          : null}
      </div>
    </Card>
  );
}

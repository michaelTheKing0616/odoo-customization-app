import { SlowHint } from "@/components/ui/craft";

export default function ConnectionLoading() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <div
        className="motion-safe:animate-pulse h-8 w-56 rounded bg-surface-muted"
        aria-hidden
      />
      <div className="rounded-md border border-border bg-surface p-6">
        <div
          className="motion-safe:animate-pulse mb-3 h-4 w-full rounded bg-surface-muted"
          aria-hidden
        />
        <div
          className="motion-safe:animate-pulse h-4 w-4/5 rounded bg-surface-muted"
          aria-hidden
        />
      </div>
      <SlowHint />
      <p className="sr-only">Loading connection</p>
    </div>
  );
}

import { SlowHint } from "@/components/ui/craft";
import { Skeleton } from "@/components/ui/layout-primitives";

export default function ConnectionLoading() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <div aria-hidden="true">
        <Skeleton className="h-8 w-56" />
      </div>
      <div aria-hidden="true" className="rounded-md border border-border bg-surface p-6">
        <Skeleton className="mb-3 h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
      </div>
      <SlowHint />
      <p className="sr-only">Loading connection</p>
    </div>
  );
}

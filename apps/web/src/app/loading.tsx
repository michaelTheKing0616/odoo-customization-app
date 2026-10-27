import { Skeleton } from "@/components/ui/layout-primitives";

export default function Loading() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-16">
      <div aria-hidden="true" className="flex flex-col gap-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-full max-w-xl" />
        <Skeleton className="h-4 w-2/3 max-w-md" />
      </div>
      <p className="sr-only">Loading page</p>
    </main>
  );
}

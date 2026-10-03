export default function Loading() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-16">
      <div
        className="motion-safe:animate-pulse h-8 w-48 rounded bg-surface-muted"
        aria-hidden
      />
      <div
        className="motion-safe:animate-pulse h-4 w-full max-w-xl rounded bg-surface-muted"
        aria-hidden
      />
      <div
        className="motion-safe:animate-pulse h-4 w-2/3 max-w-md rounded bg-surface-muted"
        aria-hidden
      />
      <p className="sr-only">Loading page</p>
    </main>
  );
}

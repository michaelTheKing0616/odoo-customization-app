import Link from "next/link";
import { Button } from "@/components/ui/Button";

/** Touch 75: an arch with one stone missing. */
export default function NotFound() {
  return (
    <main className="mx-auto flex max-w-lg flex-col items-start gap-4 px-6 py-16">
      <svg width="96" height="64" viewBox="0 0 96 64" fill="none" aria-hidden="true" className="text-muted">
        <path d="M12 60V36a36 36 0 0 1 72 0v24" stroke="currentColor" strokeWidth="2" />
        <path d="M24 60V36a24 24 0 0 1 48 0v24" stroke="currentColor" strokeWidth="2" />
        <path d="M43 1h10l-1 11h-8z" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" />
      </svg>
      <h1 className="text-lg font-semibold text-ink">This page isn&apos;t here</h1>
      <p className="text-sm text-muted">
        The link may be old or mistyped. Go home, or press <kbd className="keycap">⌘</kbd>{" "}
        <kbd className="keycap">K</kbd> to find what you need.
      </p>
      <div>
        <Button asChild variant="primary">
          <Link href="/">Go home</Link>
        </Button>
      </div>
    </main>
  );
}

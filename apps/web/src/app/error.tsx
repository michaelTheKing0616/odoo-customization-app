"use client";

import { Button } from "@/components/ui/Button";

type ErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function Error({ reset }: ErrorProps) {
  return (
    <main className="mx-auto flex max-w-lg flex-col gap-4 px-6 py-16">
      <h1 className="text-lg font-semibold text-ink">Load this page failed</h1>
      <p className="text-sm text-muted">
        The app hit an error while rendering. Try again, or return home if the problem
        continues.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="primary" onClick={() => reset()}>
          Try again
        </Button>
        <Button type="button" variant="secondary" onClick={() => window.location.assign("/")}>
          Go home
        </Button>
      </div>
    </main>
  );
}

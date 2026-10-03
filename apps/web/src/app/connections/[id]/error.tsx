"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";

type ConnectionErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ConnectionError({ reset }: ConnectionErrorProps) {
  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 p-6">
      <h1 className="text-lg font-semibold text-ink">Load this connection failed</h1>
      <p className="text-sm text-muted">
        Something blocked this connection view from rendering. Try again, or pick another
        connection from the list.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="primary" onClick={() => reset()}>
          Try again
        </Button>
        <Button asChild variant="secondary">
          <Link href="/connections">View connections</Link>
        </Button>
      </div>
    </div>
  );
}

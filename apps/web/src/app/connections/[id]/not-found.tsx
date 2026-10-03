import Link from "next/link";
import { Button } from "@/components/ui/Button";

export default function ConnectionNotFound() {
  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 p-6">
      <h1 className="text-lg font-semibold text-ink">Find this connection failed</h1>
      <p className="text-sm text-muted">
        No connection matches this id, or it was removed. Open the connections list and
        choose an active instance.
      </p>
      <div>
        <Button asChild variant="primary">
          <Link href="/connections">View connections</Link>
        </Button>
      </div>
    </div>
  );
}

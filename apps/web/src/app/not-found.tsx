import Link from "next/link";
import { Button } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <main className="mx-auto flex max-w-lg flex-col gap-4 px-6 py-16">
      <h1 className="text-lg font-semibold text-ink">Find this page failed</h1>
      <p className="text-sm text-muted">
        The URL does not match a route in Ingenium. Check the link or open the home page.
      </p>
      <div>
        <Button asChild variant="primary">
          <Link href="/">Go home</Link>
        </Button>
      </div>
    </main>
  );
}

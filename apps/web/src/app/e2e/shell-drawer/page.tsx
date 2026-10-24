import { Suspense } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { ShellProvider } from "@/context/ShellContext";
import type { Connection } from "@/lib/api";
import { QueryProvider } from "@/providers/QueryProvider";

const exampleConnection: Connection = {
  id: "example",
  name: "Example",
  url: "https://example.invalid",
  db_name: "example",
  username: "example",
  server_version: null,
  write_mode: "standard",
  is_test_copy: false,
  created_at: null,
  updated_at: null,
};

/** Example shell for the drawer oracle. Does not fetch a connection. */
export default function ShellDrawerHarnessPage() {
  return (
    <QueryProvider>
      <ShellProvider connectionId={exampleConnection.id}>
        <TooltipProvider>
          <Suspense fallback={<p className="p-4 text-sm text-ink">Example</p>}>
            <AppShell connectionId={exampleConnection.id} example={exampleConnection}>
              <p>Example</p>
            </AppShell>
          </Suspense>
        </TooltipProvider>
      </ShellProvider>
    </QueryProvider>
  );
}

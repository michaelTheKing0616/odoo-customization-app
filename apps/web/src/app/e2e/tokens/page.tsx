"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card, Kbd, PageHeader } from "@/components/ui/layout-primitives";

export default function TokensE2EPage() {
  if (process.env.NEXT_PUBLIC_E2E !== "1") {
    return <p className="p-8">E2E harness only.</p>;
  }
  return (
    <main className="min-h-screen bg-surface p-8 text-ink" data-testid="tokens-page">
      <PageHeader title="Design tokens" description="UIX-1 vision-verify harness" />
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-4">
          <h2 className="text-sm font-semibold">Neutrals & accent</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="h-8 w-8 rounded bg-surface border border-border-subtle" />
            <span className="h-8 w-8 rounded bg-surface-raised border border-border-subtle" />
            <span className="h-8 w-8 rounded bg-accent" />
            <span className="h-8 w-8 rounded bg-accent-subtle" />
          </div>
        </Card>
        <Card className="p-4">
          <h2 className="text-sm font-semibold">Typography</h2>
          <p className="text-xs text-muted">text-xs muted</p>
          <p className="text-sm">text-sm body</p>
          <p className="text-md font-semibold">text-md heading</p>
          <p className="font-mono text-sm">font-mono code</p>
        </Card>
        <Card className="p-4">
          <h2 className="text-sm font-semibold">Semantic</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant="success">Success</Badge>
            <Badge variant="warning">Warning</Badge>
            <Badge variant="danger">Danger</Badge>
            <Badge variant="info">Info</Badge>
          </div>
        </Card>
        <Card className="p-4">
          <h2 className="text-sm font-semibold">Controls</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Kbd>⌘K</Kbd>
          </div>
          <Callout variant="info" title="Token sanity" className="mt-4">
            Light and dark screenshots attach to UIX-1 gate.
          </Callout>
        </Card>
      </div>
    </main>
  );
}

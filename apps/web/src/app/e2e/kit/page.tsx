"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card, EmptyState, PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { Sheet } from "@/components/ui/Sheet";
import { IconExpert } from "@/components/ui/icons";
import { useState } from "react";

export default function KitE2EPage() {
  const [sheetOpen, setSheetOpen] = useState(false);
  if (process.env.NEXT_PUBLIC_E2E !== "1") {
    return <p className="p-8">E2E harness only.</p>;
  }
  return (
    <main className="min-h-screen bg-surface p-8" data-testid="kit-page">
      <PageHeader title="Component kit" description="UIX-2 showcase" />
      <div className="grid gap-4">
        <Card className="p-4 space-y-2">
          <Button variant="primary">Primary</Button>
          <Button variant="danger">Danger</Button>
          <Badge variant="ga">GA</Badge>
          <Callout variant="warning" title="Gating callout">
            What → why → options layout.
          </Callout>
          <Skeleton className="h-8 w-40" />
          <EmptyState
            icon={<IconExpert className="h-8 w-8" />}
            title="Empty state"
            description="Designed first-class empty copy."
            action={<Button variant="secondary">Action</Button>}
          />
          <Button variant="secondary" onClick={() => setSheetOpen(true)}>
            Open sheet
          </Button>
        </Card>
      </div>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen} title="Sheet demo">
        <div className="p-4 text-sm">Right sheet panel</div>
      </Sheet>
    </main>
  );
}

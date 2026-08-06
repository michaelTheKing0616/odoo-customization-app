"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";

/** Playwright harness — mocked ingest job with gaps blocking commit. */
export default function IngestE2EPage() {
  const [gaps] = useState([{ message: "UoM 'crates' not found on instance" }]);
  const planSteps = ["res.partner", "product.template"];

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6" data-testid="ingest-page">
      <h1 className="text-lg font-semibold">Ingest E2E harness</h1>
      <Card className="space-y-3 p-4">
        <Badge data-testid="ingest-status">planned</Badge>
        <ol className="list-decimal pl-5 text-sm" data-testid="ingest-commit-order">
          {planSteps.map((m, i) => (
            <li key={m} data-testid={`ingest-step-${i}`}>
              {m}
            </li>
          ))}
        </ol>
        <div data-testid="ingest-gaps" className="text-sm text-warning">
          {gaps[0].message}
        </div>
        <Button type="button" data-testid="ingest-commit-btn" disabled>
          Commit
        </Button>
        <p className="text-xs text-danger" data-testid="ingest-gap-block">
          Resolve gaps before commit.
        </p>
      </Card>
    </div>
  );
}

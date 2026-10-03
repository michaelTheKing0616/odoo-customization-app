"use client";

import { useParams } from "next/navigation";
import { ScanToFieldPanel } from "@/components/scanner/ScanToFieldPanel";
import { Card } from "@/components/ui/layout-primitives";
import {
  BulkPortalSection,
  BulkSecuritySection,
  BulkSendMessageSection,
} from "@/components/bulk/BulkAccessSections";
import {
  BulkActivitiesSection,
  BulkDedupeSection,
  BulkMassEditSection,
} from "@/components/bulk/BulkEditSections";
import { BulkResultsSection } from "@/components/bulk/BulkResultsSection";
import { BulkSuiteChrome } from "@/components/bulk/BulkSuiteChrome";
import { BulkSuiteConfirm } from "@/components/bulk/BulkSuiteConfirm";
import { BulkTransitionCard } from "@/components/bulk/BulkTransitionCard";
import { useBulkSuitePage } from "@/components/bulk/use-bulk-suite-page";

export default function BulkSuitePage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const vm = useBulkSuitePage(connectionId);

  return (
    <div className="mx-auto max-w-5xl" data-testid="bulk-suite-page">
      <BulkSuiteChrome vm={vm} />
      <BulkTransitionCard vm={vm} />

      <Card className="mt-6 space-y-4 p-4">
        <h2 className="text-lg font-semibold">Mass field edit</h2>
        <BulkMassEditSection vm={vm} />
      </Card>

      <Card className="mt-6 space-y-4 p-4">
        <h2 className="text-lg font-semibold">Duplicate detection & merge</h2>
        <BulkDedupeSection vm={vm} />
      </Card>

      <Card className="mt-6 space-y-4 p-4">
        <h2 className="text-lg font-semibold">Bulk activities</h2>
        <BulkActivitiesSection vm={vm} />
      </Card>

      <Card className="mt-6 space-y-4 p-4">
        <h2 className="text-lg font-semibold">Bulk security</h2>
        <BulkSecuritySection vm={vm} />
      </Card>

      <Card className="mt-6 space-y-4 p-4">
        <h2 className="text-lg font-semibold">Bulk portal access</h2>
        <BulkPortalSection vm={vm} />
      </Card>

      <Card className="mt-6 space-y-4 p-4">
        <h2 className="text-lg font-semibold">Bulk send message</h2>
        <BulkSendMessageSection vm={vm} />
      </Card>

      <BulkResultsSection vm={vm} />
      <BulkSuiteConfirm vm={vm} />
      <ScanToFieldPanel connectionId={connectionId} connection={vm.connection} defaultModel={vm.model} />
    </div>
  );
}

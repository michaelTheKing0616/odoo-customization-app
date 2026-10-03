"use client";

import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/layout-primitives";
import { Disclosure } from "@/components/ui/Disclosure";
import { ConfigCommandCenter } from "@/components/config/ConfigCommandCenter";
import { ConfigAtlasBrowser } from "@/components/config/ConfigAtlasBrowser";
import { ConfigCompanySequences } from "@/components/config/ConfigCompanySequences";
import { ConfigMailPaperDefaults } from "@/components/config/ConfigMailPaperDefaults";
import { ConfigScheduledI18n } from "@/components/config/ConfigScheduledI18n";
import { CONFIRM_PHRASE } from "@/components/config/config-types";
import { useConfigPage } from "@/components/config/use-config-page";
import { InstanceFingerprintCard } from "@/components/overview/InstanceFingerprintCard";

export default function ConfigPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const vm = useConfigPage(connectionId);

  return (
    <div className="mx-auto max-w-5xl" data-testid="config-page">
      <PageHeader
        title="Instance Config"
        description="Recipe Command Center · Day-1 · numbering · apps · expert controls"
      />
      <VersionAwarenessBanner capabilities={vm.connection?.capabilities} />

      <InstanceFingerprintCard connectionId={connectionId} context="config" />

      <ConfigCommandCenter connectionId={connectionId} />
      <div className="mt-10" data-testid="config-atlas-section">
        <h2 className="mb-3 text-ui-display font-semibold text-ink">Config Atlas</h2>
        <ConfigAtlasBrowser connectionId={connectionId} />
      </div>


      {vm.error ? <ErrorNotice message={vm.error} className="mt-4" /> : null}
      {vm.notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {vm.notice}
        </Callout>
      ) : null}

      {vm.mailHealth ? (
        <Callout
          variant={vm.mailHealth.ok ? "info" : "warning"}
          title="Mail health"
          className="mt-4"
          testId="config-mail-health"
        >
          {vm.mailHealth.ok
            ? `${vm.mailHealth.smtp_servers} outgoing mail server(s), ${vm.mailHealth.alias_domains} alias domain(s). Passwords stay in Odoo.`
            : vm.mailHealth.warnings[0] ||
              "No outgoing mail server. Paste SMTP in Odoo — this app never stores the password."}
        </Callout>
      ) : null}

      <Disclosure title="Expert controls" testId="config-expert-controls" className="mt-8">
        <ConfigCompanySequences vm={vm} />
        <ConfigMailPaperDefaults vm={vm} />
        <ConfigScheduledI18n vm={vm} />
      </Disclosure>

      <ConfirmDialogV2
        open={vm.deactivateCron != null}
        riskLevel="danger"
        title="Deactivate scheduled action"
        warning={
          vm.deactivateCron
            ? `Stop ir.cron #${vm.deactivateCron.id} (${vm.deactivateCron.name}) on the live database.`
            : ""
        }
        risks={[
          "Background jobs stop until re-enabled",
          "Dependent processes may stall",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={vm.busy}
        onCancel={() => vm.setDeactivateCron(null)}
        onConfirm={(phrase) => {
          const deactivateCron = vm.deactivateCron;
          if (!deactivateCron) return;
          void (async () => {
            vm.setBusy(true);
            try {
              await api.patchIrCronActive(connectionId, deactivateCron.id, {
                active: false,
                confirm_advanced: true,
                confirm_phrase: phrase,
              });
              vm.setNotice(`Deactivated cron #${deactivateCron.id}`);
              vm.setDeactivateCron(null);
              await vm.refresh();
            } catch (err) {
              vm.setError(err instanceof Error ? err.message : "Deactivate failed");
            } finally {
              vm.setBusy(false);
            }
          })();
        }}
      />
    </div>
  );
}

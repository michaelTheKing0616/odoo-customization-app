"use client";

import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Callout } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/layout-primitives";
import { Disclosure } from "@/components/ui/Disclosure";
import { ConfigCommandCenter } from "@/components/config/ConfigCommandCenter";
import { ConfigAtlasBrowser } from "@/components/config/ConfigAtlasBrowser";
import { ConfigCompanySequences } from "@/components/config/ConfigCompanySequences";
import { ConfigMailPaperDefaults } from "@/components/config/ConfigMailPaperDefaults";
import { ConfigScheduledI18n } from "@/components/config/ConfigScheduledI18n";
import { ConfigErrorNotice } from "@/components/config/ConfigErrorNotice";
import { CONFIRM_PHRASE } from "@/components/config/config-types";
import { useConfigPage } from "@/components/config/use-config-page";
import { InstanceFingerprintCard } from "@/components/overview/InstanceFingerprintCard";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  sanitizeConfigCopy,
} from "@/lib/configScreen";
import "@/components/config/config-operate.css";

export default function ConfigPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const vm = useConfigPage(connectionId);

  return (
    <div className="config-operate" data-testid="config-page">
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} />
      <VersionAwarenessBanner capabilities={vm.connection?.capabilities} />

      <InstanceFingerprintCard connectionId={connectionId} context="config" />

      <ConfigCommandCenter connectionId={connectionId} />

      <div className="cfg-atlas" data-testid="config-atlas-section">
        <h2 className="cfg-panel-title">Config Atlas</h2>
        <p className="cfg-panel-sub">
          Browse intents by class. Preview is not posted or confirmed. L3 lock dates need confirm.
        </p>
        <ConfigAtlasBrowser connectionId={connectionId} />
      </div>

      {vm.error ? (
        <ConfigErrorNotice
          className="mt-4"
          message={vm.error}
          context="load"
          onDismiss={() => vm.setError(null)}
        />
      ) : null}
      {vm.notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {sanitizeConfigCopy(vm.notice)}
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
            : sanitizeConfigCopy(
                vm.mailHealth.warnings[0] ||
                  "No outgoing mail server. Paste SMTP in Odoo - this app never stores the password.",
              )}
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

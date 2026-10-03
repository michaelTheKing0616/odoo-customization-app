import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { CONFIRM_PHRASE } from "./bulk-helpers";
import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkSuiteConfirm({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <ConfirmDialogV2
      open={vm.confirmOpen}
      riskLevel="danger"
      phrase={CONFIRM_PHRASE}
      title={
        vm.confirmMode === "mass_edit"
          ? "Confirm mass field edit"
          : vm.confirmMode === "dedupe_merge"
            ? "Confirm duplicate merge"
            : vm.confirmMode === "activities"
              ? "Confirm bulk activities"
              : vm.confirmMode === "security"
                ? "Confirm security apply"
                : vm.confirmMode === "portal"
                  ? "Confirm portal batch"
                  : vm.confirmMode === "send_message"
                    ? "Confirm bulk send message"
                    : "Confirm bulk transition"
      }
      warning={
        vm.confirmMode === "mass_edit"
          ? `This will write field values on live ${vm.model} records. Dry-run first when unsure.`
          : vm.confirmMode === "dedupe_merge"
            ? `Merge ${vm.loserIds.length} duplicate(s) into winner #${vm.winnerId ?? "?"} on ${vm.model}.`
            : vm.confirmMode === "activities"
              ? `Schedule activities on live ${vm.model} records.`
              : vm.confirmMode === "security"
                ? `Apply security changes (${vm.securityMode}) on selected users.`
                : vm.confirmMode === "portal"
                  ? `Portal ${vm.portalAction} on selected partners.`
                  : vm.confirmMode === "send_message"
                    ? `Post threaded messages on live ${vm.model} records.`
                    : vm.selectedButton
                    ? `This will call ${vm.method} on live ${vm.model} records. Dry-run first when unsure.`
                    : "Bulk workflow transition on live ERP data."
      }
      risks={
        vm.confirmMode === "mass_edit"
          ? [
              "Batch write on live ERP records",
              "Protected-module policy blocks tier-1 and non-x_* fields on tier-2",
            ]
          : vm.confirmMode === "dedupe_merge"
            ? [
                "Partially reversible — snapshot stored but manual recovery may be needed",
                "Inbound FK rows and chatter are rewritten; losers archived by default",
              ]
            : vm.confirmMode === "activities"
              ? [
                  "Creates mail.activity rows and may notify assignees",
                  "Requires mail.activity.mixin on the target model",
                ]
              : vm.confirmMode === "security"
                ? [
                    "Changes res.users group membership immediately",
                    "Adding groups may imply additional groups (not edited directly)",
                  ]
                : vm.confirmMode === "portal"
                  ? [
                      "Grant may create portal users and send access emails",
                      "Partners without email are skipped individually on grant",
                    ]
                  : vm.confirmMode === "send_message"
                    ? [
                        "One message_post per record — not mass-mail composer",
                        "Template renders per record when mail_template_id is set",
                      ]
                    : [
                      "Runs as the connected Odoo user — side effects may include mail, stock, or accounting",
                      "Successful rows are not auto-undone if some records fail",
                    ]
      }
      busy={vm.busy}
      onCancel={() => vm.setConfirmOpen(false)}
      onConfirm={(phrase) =>
        void (vm.confirmMode === "mass_edit"
          ? vm.runMassEdit(false, phrase)
          : vm.confirmMode === "dedupe_merge"
            ? vm.mergeDedupe(false, phrase)
            : vm.confirmMode === "activities"
              ? vm.runActivities(false, phrase)
              : vm.confirmMode === "security"
                ? vm.applySecurity(false, phrase)
                : vm.confirmMode === "portal"
                  ? vm.runPortal(false, phrase)
                  : vm.confirmMode === "send_message"
                    ? vm.runSendMessage(false, phrase)
                    : vm.run(false, phrase))
      }
    />
  );
}

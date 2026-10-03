"use client";

import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { CONFIRM_PHRASE } from "./studio-constants";
import type { StudioPageModel } from "./use-studio-page";

export function StudioConfirmDialogs(vm: StudioPageModel) {
  return (
    <>
      <ConfirmDialogV2
        open={vm.installOpen}
        title="Install Invoicing on this connection"
        warning="Installs Community Invoicing (account) on this live Odoo so Accounting Settings exist. Sandbox prove did not do that."
        risks={[
          "Installs the stock account module and its depends",
          "Does not install CBN — Promote the zip after this",
          "Settings → search Currency remains an Enterprise tease until Promote",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={vm.busy === "install-host"}
        riskLevel="danger"
        snapshotNote="Prefer a sandbox connection before production."
        onCancel={() => vm.setInstallOpen(false)}
        onConfirm={(phrase) => void vm.installGoldHostModule(phrase)}
      />
      <ConfirmDialogV2
        open={vm.promoteOpen}
        title="Promote validated module"
        warning="Installs the sandbox-validated Python module on this live Odoo connection. The ephemeral sandbox is already gone."
        risks={
          vm.authoredOptionA
            ? [
                "Adds Python/XML on stock models (for example sale.order markup)",
                "Does not create a new home-grid tile — inspect the stock Sales form",
                "Never invents account.tax — WHT must use an existing tax xmlid",
                "Only promote after sandbox validation passed (2 hour token)",
              ]
            : [
                "Adds Python, views, and cron jobs (CBN writes stock res.currency.rate)",
                "Does not create a new app tile — inspect Accounting Settings after",
                "Uninstall may not fully reverse rates or cron",
                "Only promote after sandbox validation passed (2 hour token)",
              ]
        }
        phrase={CONFIRM_PHRASE}
        busy={vm.busy === "promote"}
        riskLevel="danger"
        snapshotNote="Prefer a sandbox connection before production. Promote stays human."
        onCancel={() => vm.setPromoteOpen(false)}
        onConfirm={(phrase) => void vm.promoteGoldModule(phrase)}
      />
      <ConfirmDialogV2
        open={vm.applyOpen}
        title={vm.fieldPack ? "Add these fields in Odoo" : "Apply draft to Odoo"}
        warning={
          vm.fieldPack
            ? `Adds the fields on this preview to the existing ${vm.hostFormName} form. Does not create a new app on the home screen.`
            : "Applies this App Studio draft: models, fields, views, menus, and smart buttons on the live connection."
        }
        risks={
          vm.fieldPack
            ? [
                `Adds fields on the stock ${vm.hostFormName} form via RPC`,
                "Does not create a new home-grid tile",
                "Prefer a sandbox connection before production",
                ...(vm.isOdooOnline
                  ? ["Odoo Online: no custom Python module install — metadata apply only"]
                  : []),
              ]
            : [
                "Creates ir.model / fields / views / menus via RPC",
                "May rewrite primary form arches for custom x_* models",
                "Prefer a sandbox connection before production",
                ...(vm.isOdooOnline
                  ? ["Odoo Online: no custom Python module install — metadata apply only"]
                  : []),
              ]
        }
        phrase={CONFIRM_PHRASE}
        busy={vm.busy === "apply"}
        riskLevel="danger"
        snapshotNote="Take a metadata snapshot first if this is production."
        onCancel={() => vm.setApplyOpen(false)}
        onConfirm={(phrase) => void vm.onApplyToOdoo(phrase)}
      />
    </>
  );
}

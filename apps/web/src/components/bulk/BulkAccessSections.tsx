import { Button } from "@/components/ui/Button";
import { DRY_RUN_CTA } from "@/lib/bulkSuiteScreen";
import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkSecuritySection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="bu-panel-sub">
        Preview group membership changes first. Implied groups are warned, never edited.
      </p>
      <div className="bu-field-grid bu-cols-2">
        <label className="bu-field">
          User ids
          <input
            className="font-mono"
            value={vm.securityUserIds}
            onChange={(e) => vm.setSecurityUserIds(e.target.value)}
            placeholder="2, 5"
          />
        </label>
        <label className="bu-field">
          Mode
          <select
            value={vm.securityMode}
            onChange={(e) =>
              vm.setSecurityMode(e.target.value as "add" | "remove" | "offboard")
            }
          >
            <option value="add">Add to groups</option>
            <option value="remove">Remove from groups</option>
            <option value="offboard">Offboard (strip non-base groups)</option>
          </select>
        </label>
        {vm.securityMode !== "offboard" ? (
          <label className="bu-field" style={{ gridColumn: "1 / -1" }}>
            Group ids
            <input
              className="font-mono"
              value={vm.securityGroupIds}
              onChange={(e) => vm.setSecurityGroupIds(e.target.value)}
              placeholder="8, 12"
            />
          </label>
        ) : null}
        {vm.securityMode === "offboard" ? (
          <label className="bu-inline" style={{ gridColumn: "1 / -1" }}>
            <input
              type="checkbox"
              checked={vm.securityOffboardDeactivate}
              onChange={(e) => vm.setSecurityOffboardDeactivate(e.target.checked)}
            />
            Also deactivate users
          </label>
        ) : null}
      </div>
      <div className="bu-actions">
        <Button type="button" variant="secondary" disabled={vm.busy} onClick={() => void vm.previewSecurity()}>
          Preview diff
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={vm.busy || !vm.securityPreview}
          onClick={() => void vm.applySecurity(true)}
        >
          {DRY_RUN_CTA} apply
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={vm.busy || !vm.securityPreview}
          onClick={() => void vm.applySecurity(false)}
        >
          Apply
        </Button>
      </div>
      {vm.securityPreview ? (
        <div className="bu-table-wrap mt-3" data-testid="bulk-security-preview">
          <p className="px-3 pt-3 text-sm font-medium text-ink">{vm.securityPreview.message}</p>
          {vm.securityPreview.users.map((u) => (
            <div key={u.user_id} className="border-t border-border-subtle px-3 py-2 text-sm">
              <div>
                {u.user_name} (#{u.user_id})
              </div>
              {u.add_groups.length > 0 ? (
                <div className="text-xs text-muted">
                  Add: {u.add_groups.map((g) => g.name).join(", ")}
                </div>
              ) : null}
              {u.remove_groups.length > 0 ? (
                <div className="text-xs text-muted">
                  Remove: {u.remove_groups.map((g) => g.name).join(", ")}
                </div>
              ) : null}
              {u.implied_warnings.map((w) => (
                <div key={w} className="bu-safe" data-tone="danger">
                  {w}
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : null}
    </>
  );
}

export function BulkPortalSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="bu-panel-sub">
        Grant or revoke portal access for partners. Missing email fails per partner, not the batch.
      </p>
      <label className="bu-field">
        Partner ids
        <input
          className="font-mono"
          value={vm.portalPartnerIds}
          onChange={(e) => vm.setPortalPartnerIds(e.target.value)}
          placeholder="14, 18"
        />
      </label>
      <label className="bu-field">
        Action
        <select
          value={vm.portalAction}
          onChange={(e) => vm.setPortalAction(e.target.value as "grant" | "revoke")}
        >
          <option value="grant">Grant portal</option>
          <option value="revoke">Revoke portal</option>
        </select>
      </label>
      <div className="bu-actions">
        <Button type="button" variant="secondary" disabled={vm.busy} onClick={() => void vm.runPortal(true)}>
          {DRY_RUN_CTA}
        </Button>
        <Button type="button" variant="primary" disabled={vm.busy} onClick={() => void vm.runPortal(false)}>
          Execute
        </Button>
      </div>
    </>
  );
}

export function BulkSendMessageSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="bu-panel-sub">
        Post one threaded message per record via message_post. Not Odoo mass-mail composer.
        Target records with ids or domain above.
      </p>
      <label className="bu-field">
        Subject
        <input value={vm.sendSubject} onChange={(e) => vm.setSendSubject(e.target.value)} />
      </label>
      <label className="bu-field">
        Body (HTML)
        <textarea
          rows={3}
          value={vm.sendBody}
          onChange={(e) => vm.setSendBody(e.target.value)}
        />
      </label>
      <label className="bu-field">
        Mail template id (optional)
        <input
          className="font-mono"
          value={vm.sendTemplateId}
          onChange={(e) => vm.setSendTemplateId(e.target.value)}
          placeholder="12"
        />
      </label>
      <div className="bu-actions">
        <Button type="button" variant="secondary" disabled={vm.busy} onClick={() => void vm.runSendMessage(true)}>
          {DRY_RUN_CTA}
        </Button>
        <Button type="button" variant="primary" disabled={vm.busy} onClick={() => void vm.runSendMessage(false)}>
          Send
        </Button>
      </div>
    </>
  );
}

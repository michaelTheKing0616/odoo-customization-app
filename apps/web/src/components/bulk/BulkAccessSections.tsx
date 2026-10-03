import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkSecuritySection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="text-sm text-[var(--odoo-muted)]">
        Preview group membership changes first — implied groups are warned, never edited.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block text-sm">
          User ids
          <input
            className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-sm"
            value={vm.securityUserIds}
            onChange={(e) => vm.setSecurityUserIds(e.target.value)}
            placeholder="2, 5"
          />
        </label>
        <label className="block text-sm">
          Mode
          <select
            className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5"
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
        {vm.securityMode !== "offboard" && (
          <label className="block text-sm md:col-span-2">
            Group ids
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-sm"
              value={vm.securityGroupIds}
              onChange={(e) => vm.setSecurityGroupIds(e.target.value)}
              placeholder="8, 12"
            />
          </label>
        )}
        {vm.securityMode === "offboard" && (
          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input
              type="checkbox"
              checked={vm.securityOffboardDeactivate}
              onChange={(e) => vm.setSecurityOffboardDeactivate(e.target.checked)}
            />
            Also deactivate users
          </label>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="odoo-btn-secondary" disabled={vm.busy} onClick={() => void vm.previewSecurity()}>
          Preview diff
        </button>
        <button type="button" className="odoo-btn-secondary" disabled={vm.busy || !vm.securityPreview} onClick={() => void vm.applySecurity(true)}>
          Dry run apply
        </button>
        <button type="button" className="odoo-btn-primary" disabled={vm.busy || !vm.securityPreview} onClick={() => void vm.applySecurity(false)}>
          Apply
        </button>
      </div>
      {vm.securityPreview && (
        <div className="rounded border border-[var(--odoo-border)] p-3 text-sm">
          <p className="font-medium">{vm.securityPreview.message}</p>
          {vm.securityPreview.users.map((u) => (
            <div key={u.user_id} className="mt-2 border-t border-[var(--odoo-border)]/60 pt-2">
              <div>{u.user_name} (#{u.user_id})</div>
              {u.add_groups.length > 0 && (
                <div className="text-xs text-[var(--odoo-muted)]">
                  Add: {u.add_groups.map((g) => g.name).join(", ")}
                </div>
              )}
              {u.remove_groups.length > 0 && (
                <div className="text-xs text-[var(--odoo-muted)]">
                  Remove: {u.remove_groups.map((g) => g.name).join(", ")}
                </div>
              )}
              {u.implied_warnings.map((w) => (
                <div key={w} className="text-xs text-amber-800">
                  {w}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export function BulkPortalSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="text-sm text-[var(--odoo-muted)]">
        Grant or revoke portal access for partners — missing email fails per partner, not the batch.
      </p>
      <label className="block text-sm">
        Partner ids
        <input
          className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-sm"
          value={vm.portalPartnerIds}
          onChange={(e) => vm.setPortalPartnerIds(e.target.value)}
          placeholder="14, 18"
        />
      </label>
      <label className="block text-sm">
        Action
        <select
          className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5"
          value={vm.portalAction}
          onChange={(e) => vm.setPortalAction(e.target.value as "grant" | "revoke")}
        >
          <option value="grant">Grant portal</option>
          <option value="revoke">Revoke portal</option>
        </select>
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="odoo-btn-secondary" disabled={vm.busy} onClick={() => void vm.runPortal(true)}>
          Dry run
        </button>
        <button type="button" className="odoo-btn-primary" disabled={vm.busy} onClick={() => void vm.runPortal(false)}>
          Execute
        </button>
      </div>
    </>
  );
}

export function BulkSendMessageSection({ vm }: { vm: BulkSuitePageModel }) {
  return (
    <>
      <p className="text-sm text-[var(--odoo-muted)]">
        Post one threaded message per record via message_post — not Odoo mass-mail composer.
        Target records with ids or domain above.
      </p>
      <label className="block text-sm">
        Subject
        <input
          className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5"
          value={vm.sendSubject}
          onChange={(e) => vm.setSendSubject(e.target.value)}
        />
      </label>
      <label className="block text-sm">
        Body (HTML)
        <textarea
          className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-sm"
          rows={3}
          value={vm.sendBody}
          onChange={(e) => vm.setSendBody(e.target.value)}
        />
      </label>
      <label className="block text-sm">
        Mail template id (optional)
        <input
          className="mt-1 w-full border border-[var(--odoo-border)] bg-surface px-2 py-1.5 font-mono text-sm"
          value={vm.sendTemplateId}
          onChange={(e) => vm.setSendTemplateId(e.target.value)}
          placeholder="12"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="odoo-btn-secondary" disabled={vm.busy} onClick={() => void vm.runSendMessage(true)}>
          Dry run
        </button>
        <button type="button" className="odoo-btn-primary" disabled={vm.busy} onClick={() => void vm.runSendMessage(false)}>
          Send
        </button>
      </div>
    </>
  );
}

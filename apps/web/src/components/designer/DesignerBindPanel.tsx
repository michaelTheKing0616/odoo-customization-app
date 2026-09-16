"use client";

import type { ActivityTypeRow, Connection, FieldRow, MailTemplateRow } from "@/lib/api";
import {
  bindModeSupported,
  bindModeUnsupportedReason,
} from "@/lib/capabilities";
import type { BindDialogMode, ButtonPlacement } from "@/components/designer/designer-model";
import { parseSelectionOptions } from "@/components/designer/designer-model";

export type BindableAction = {
  id: number;
  name: string;
  action_type: "ir.actions.server" | "ir.actions.act_window";
  model: string;
  detail: string | null;
};

export type DesignerBindPanelProps = {
  connection: Connection | null;
  fields: FieldRow[];
  bindMode: Exclude<BindDialogMode, "closed">;
  bindPlacement: ButtonPlacement;
  bindLabel: string;
  setBindLabel: (v: string) => void;
  bindFieldName: string;
  setBindFieldName: (v: string) => void;
  bindValue: string;
  setBindValue: (v: string) => void;
  bindTargetModel: string;
  setBindTargetModel: (v: string) => void;
  bindRelationField: string;
  setBindRelationField: (v: string) => void;
  bindIcon: string;
  setBindIcon: (v: string) => void;
  bindCreateCountField: boolean;
  setBindCreateCountField: (v: boolean) => void;
  bindOne2manyField: string;
  setBindOne2manyField: (v: string) => void;
  bindCountFieldName: string;
  setBindCountFieldName: (v: string) => void;
  bindSmartConfirmPhrase: string;
  setBindSmartConfirmPhrase: (v: string) => void;
  selectedActionId: number | "";
  setSelectedActionId: (v: number | "") => void;
  bindableActions: BindableAction[];
  activityTypes: ActivityTypeRow[];
  mailTemplates: MailTemplateRow[];
  bindActivityTypeId: number | "";
  setBindActivityTypeId: (v: number | "") => void;
  bindActivitySummary: string;
  setBindActivitySummary: (v: string) => void;
  bindActivityNote: string;
  setBindActivityNote: (v: string) => void;
  bindMailTemplateId: number | "";
  setBindMailTemplateId: (v: number | "") => void;
  bindMailMethod: "email" | "comment" | "note";
  setBindMailMethod: (v: "email" | "comment" | "note") => void;
  bindMailSubject: string;
  setBindMailSubject: (v: string) => void;
  bindMailBody: string;
  setBindMailBody: (v: string) => void;
  bindMailEmailTo: string;
  setBindMailEmailTo: (v: string) => void;
  busy: boolean;
  confirmPhrase: string;
  openBindDialog: (placement: ButtonPlacement, mode: BindDialogMode) => void;
  onSubmitBind: (opts?: { confirm_advanced?: boolean; confirm_phrase?: string }) => void;
  onClose: () => void;
};

export function DesignerBindPanel({
  connection,
  fields,
  bindMode,
  bindPlacement,
  bindLabel,
  setBindLabel,
  bindFieldName,
  setBindFieldName,
  bindValue,
  setBindValue,
  bindTargetModel,
  setBindTargetModel,
  bindRelationField,
  setBindRelationField,
  bindIcon,
  setBindIcon,
  bindCreateCountField,
  setBindCreateCountField,
  bindOne2manyField,
  setBindOne2manyField,
  bindCountFieldName,
  setBindCountFieldName,
  bindSmartConfirmPhrase,
  setBindSmartConfirmPhrase,
  selectedActionId,
  setSelectedActionId,
  bindableActions,
  activityTypes,
  mailTemplates,
  bindActivityTypeId,
  setBindActivityTypeId,
  bindActivitySummary,
  setBindActivitySummary,
  bindActivityNote,
  setBindActivityNote,
  bindMailTemplateId,
  setBindMailTemplateId,
  bindMailMethod,
  setBindMailMethod,
  bindMailSubject,
  setBindMailSubject,
  bindMailBody,
  setBindMailBody,
  bindMailEmailTo,
  setBindMailEmailTo,
  busy,
  confirmPhrase,
  openBindDialog,
  onSubmitBind,
  onClose,
}: DesignerBindPanelProps) {
  return (
          <div className="mt-4 border border-border-subtle/40 bg-surface-muted p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-muted">
                Bind {bindPlacement} button to a real Odoo action
              </p>
              <div className="flex flex-wrap gap-2 text-xs">
                {(
                  [
                    ["create_update", "Update field"],
                    ["create_related", "Open related"],
                    ["create_activity", "Next activity"],
                    ["create_mail", "Send mail"],
                    ["create_smart", "Smart button"],
                    ["bind_existing", "Existing action"],
                  ] as const
                ).map(([mode, label]) => {
                  const allowed = bindModeSupported(connection, mode);
                  const reason = bindModeUnsupportedReason(connection, mode);
                  return (
                    <button
                      key={mode}
                      type="button"
                      disabled={!allowed}
                      title={reason ?? undefined}
                      className={
                        !allowed
                          ? "cursor-not-allowed text-muted opacity-50"
                          : bindMode === mode
                            ? "text-muted"
                            : "text-muted"
                      }
                      onClick={() => {
                        if (!allowed) return;
                        openBindDialog(bindPlacement, mode);
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
              {!bindModeSupported(connection, bindMode) && (
                <p className="mt-2 w-full text-[11px] text-warning">
                  {bindModeUnsupportedReason(connection, bindMode)}
                </p>
              )}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs text-muted">
                Button label
                <input
                  value={bindLabel}
                  onChange={(e) => setBindLabel(e.target.value)}
                  className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                />
              </label>
              {bindMode === "create_update" && (
                <>
                  <label className="text-xs text-muted">
                    Field to update
                    <select
                      value={bindFieldName}
                      onChange={(e) => {
                        const name = e.target.value;
                        setBindFieldName(name);
                        const meta = fields.find((f) => f.name === name);
                        const opts = parseSelectionOptions(meta?.selection);
                        if (opts[0]) setBindValue(opts[0].value);
                      }}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm"
                    >
                      <option value="">Select field…</option>
                      {fields
                        .filter((f) =>
                          ["char", "text", "selection", "boolean", "integer", "float"].includes(
                            f.ttype,
                          ),
                        )
                        .map((f) => (
                          <option key={f.id} value={f.name}>
                            {f.name} · {f.ttype}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="text-xs text-muted">
                    New value
                    {(() => {
                      const opts = parseSelectionOptions(
                        fields.find((f) => f.name === bindFieldName)?.selection,
                      );
                      if (opts.length) {
                        return (
                          <select
                            value={bindValue}
                            onChange={(e) => setBindValue(e.target.value)}
                            className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                          >
                            {opts.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label} ({o.value})
                              </option>
                            ))}
                          </select>
                        );
                      }
                      return (
                        <input
                          value={bindValue}
                          onChange={(e) => setBindValue(e.target.value)}
                          className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                        />
                      );
                    })()}
                  </label>
                </>
              )}
              {(bindMode === "create_related" || bindMode === "create_smart") && (
                <>
                  <label className="text-xs text-muted">
                    Target model
                    <input
                      value={bindTargetModel}
                      onChange={(e) => setBindTargetModel(e.target.value)}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm"
                    />
                  </label>
                  <label className="text-xs text-muted">
                    Relation field on target
                    <input
                      value={bindRelationField}
                      onChange={(e) => setBindRelationField(e.target.value)}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm"
                    />
                  </label>
                  {(bindPlacement === "button_box" || bindMode === "create_smart") && (
                    <label className="text-xs text-muted">
                      Icon (Font Awesome)
                      <input
                        value={bindIcon}
                        onChange={(e) => setBindIcon(e.target.value)}
                        className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm"
                      />
                    </label>
                  )}
                </>
              )}
              {bindMode === "create_smart" && (
                <>
                  <label className="flex items-center gap-2 text-xs text-muted sm:col-span-2">
                    <input
                      type="checkbox"
                      checked={bindCreateCountField}
                      onChange={(e) => setBindCreateCountField(e.target.checked)}
                    />
                    Create computed count field (advanced — confirm required)
                  </label>
                  {bindCreateCountField && (
                    <>
                      <label className="text-xs text-muted">
                        One2many field on source
                        <input
                          value={bindOne2manyField}
                          onChange={(e) => setBindOne2manyField(e.target.value)}
                          placeholder="x_loan_ids"
                          className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm"
                        />
                      </label>
                      <label className="text-xs text-muted">
                        Count field name (optional)
                        <input
                          value={bindCountFieldName}
                          onChange={(e) => setBindCountFieldName(e.target.value)}
                          placeholder="x_loan_count"
                          className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm"
                        />
                      </label>
                      <label className="text-xs text-muted sm:col-span-2">
                        Confirm phrase
                        <input
                          value={bindSmartConfirmPhrase}
                          onChange={(e) => setBindSmartConfirmPhrase(e.target.value)}
                          placeholder={confirmPhrase}
                          className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                        />
                      </label>
                    </>
                  )}
                </>
              )}
              {bindMode === "create_activity" && (
                <>
                  <label className="text-xs text-muted">
                    Activity type
                    <select
                      value={bindActivityTypeId === "" ? "" : String(bindActivityTypeId)}
                      onChange={(e) =>
                        setBindActivityTypeId(e.target.value ? Number(e.target.value) : "")
                      }
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                    >
                      <option value="">Select…</option>
                      {activityTypes.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs text-muted">
                    Summary
                    <input
                      value={bindActivitySummary}
                      onChange={(e) => setBindActivitySummary(e.target.value)}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                    />
                  </label>
                  <label className="text-xs text-muted sm:col-span-2">
                    Note (optional)
                    <input
                      value={bindActivityNote}
                      onChange={(e) => setBindActivityNote(e.target.value)}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                    />
                  </label>
                </>
              )}
              {bindMode === "create_mail" && (
                <>
                  <label className="text-xs text-muted">
                    Mail template (optional)
                    <select
                      value={bindMailTemplateId === "" ? "" : String(bindMailTemplateId)}
                      onChange={(e) =>
                        setBindMailTemplateId(e.target.value ? Number(e.target.value) : "")
                      }
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                    >
                      <option value="">None</option>
                      {mailTemplates.map((t) => (
                        <option key={t.id} value={t.id}>
                          #{t.id} · {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs text-muted">
                    Method
                    <select
                      value={bindMailMethod}
                      onChange={(e) =>
                        setBindMailMethod(e.target.value as "email" | "comment" | "note")
                      }
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                    >
                      <option value="email">email</option>
                      <option value="comment">comment</option>
                      <option value="note">note</option>
                    </select>
                  </label>
                  <label className="text-xs text-muted">
                    Subject
                    <input
                      value={bindMailSubject}
                      onChange={(e) => setBindMailSubject(e.target.value)}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                    />
                  </label>
                  <label className="text-xs text-muted">
                    Email to
                    <input
                      value={bindMailEmailTo}
                      onChange={(e) => setBindMailEmailTo(e.target.value)}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                    />
                  </label>
                  <label className="text-xs text-muted sm:col-span-2">
                    Body HTML
                    <textarea
                      value={bindMailBody}
                      onChange={(e) => setBindMailBody(e.target.value)}
                      rows={3}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 font-mono text-xs"
                    />
                  </label>
                </>
              )}
              {bindMode === "bind_existing" && (
                <label className="text-xs text-muted sm:col-span-2">
                  Action
                  <select
                    value={selectedActionId === "" ? "" : String(selectedActionId)}
                    onChange={(e) =>
                      setSelectedActionId(e.target.value ? Number(e.target.value) : "")
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-sm"
                  >
                    <option value="">Select…</option>
                    {bindableActions.map((a) => (
                      <option key={`${a.action_type}-${a.id}`} value={a.id}>
                        #{a.id} · {a.action_type} · {a.name}
                        {a.detail ? ` (${a.detail})` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            <p className="mt-2 text-xs text-muted">
              Uses type=&quot;action&quot; + action id. Python methods (type=object) need Option A
              modules. Code/webhook server actions stay blocked here. Form-bound mail/activity
              live here; model automations live under Automations.
            </p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                disabled={busy || !bindModeSupported(connection, bindMode)}
                title={
                  bindModeUnsupportedReason(connection, bindMode) ?? undefined
                }
                onClick={() => void onSubmitBind(
                    bindMode === "create_smart" && bindCreateCountField
                      ? {
                          confirm_advanced: true,
                          confirm_phrase: bindSmartConfirmPhrase || confirmPhrase,
                        }
                      : undefined,
                  )}
                className="border border-border-subtle px-3 py-1.5 text-sm text-muted disabled:opacity-50"
              >
                Create &amp; bind
              </button>
              <button
                type="button"
                onClick={onClose}
                className="border border-border-subtle px-3 py-1.5 text-sm text-muted"
              >
                Cancel
              </button>
            </div>
          </div>
  );
}

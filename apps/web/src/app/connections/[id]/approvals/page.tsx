"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { ApprovalProcessesPanel } from "@/components/approvals/ApprovalProcessesPanel";
import { ApprovalRuleComposer } from "@/components/approvals/ApprovalRuleComposer";
import { ApprovalRulesList } from "@/components/approvals/ApprovalRulesList";
import { ApprovalEntriesList } from "@/components/approvals/ApprovalEntriesList";
import { ApprovalsStateGuide } from "@/components/approvals/ApprovalsStateGuide";
import { Callout } from "@/components/ui/Callout";
import { Button } from "@/components/ui/Button";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import { Tabs } from "@/components/ui/Tabs";
import {
  api,
  ApprovalButton,
  ApprovalEntry,
  ApprovalRule,
  ApprovalsGateResponse,
  Connection,
} from "@/lib/api";
import {
  INBOX_HINT,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  approvalsErrorGuide,
  approvalsHonestyGuide,
  approvalsSessionBadge,
  defaultApprovalRuleForm,
  engineChipLabel,
  engineHint,
  parseRecordId,
  parseUserId,
  sanitizeApprovalsCopy,
  type ApprovalRuleForm,
  type ApprovalsTab,
} from "@/lib/approvalScreen";
import "@/components/approvals/approvals-operate.css";

export default function ApprovalsPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const [tab, setTab] = useState<ApprovalsTab>("buttons");

  const [connection, setConnection] = useState<Connection | null>(null);
  const [gate, setGate] = useState<ApprovalsGateResponse | null>(null);
  const [rules, setRules] = useState<ApprovalRule[]>([]);
  const [entries, setEntries] = useState<ApprovalEntry[]>([]);
  const [buttons, setButtons] = useState<ApprovalButton[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [errorContext, setErrorContext] = useState<"load" | "deploy" | "check" | "resolve">("load");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listHydrated, setListHydrated] = useState(false);
  const [listQuery, setListQuery] = useState("");
  const [form, setForm] = useState<ApprovalRuleForm>(() => defaultApprovalRuleForm());

  const refresh = useCallback(async () => {
    const [conn, g, r, e] = await Promise.all([
      api.getConnection(connectionId),
      api.getApprovalsGate(connectionId),
      api.listApprovalRules(connectionId),
      api.listApprovalEntries(connectionId),
    ]);
    setConnection(conn);
    setGate(g);
    setRules(r);
    setEntries(e);
  }, [connectionId]);

  useEffect(() => {
    setListHydrated(false);
    refresh()
      .catch((err: Error) => {
        setErrorContext("load");
        setError(err.message);
      })
      .finally(() => setListHydrated(true));
  }, [refresh]);

  async function loadButtons() {
    setError(null);
    try {
      const rows = await api.listApprovalButtons(connectionId, form.model.trim());
      setButtons(rows);
      if (rows.length > 0 && !form.buttonMethod) {
        setForm((f) => ({ ...f, buttonMethod: rows[0].name }));
      }
    } catch (err) {
      setErrorContext("load");
      setError(err instanceof Error ? err.message : "Button discovery failed");
    }
  }

  async function onDeploy(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const selected = buttons.find((b) => b.name === form.buttonMethod);
      await api.createApprovalRule(connectionId, {
        name: form.name,
        target_model: form.model.trim(),
        button_method: form.buttonMethod,
        button_label: selected?.label ?? form.buttonMethod,
        engine: gate?.engine === "studio" ? "studio" : "community",
        steps: [
          {
            order: 1,
            approver_user_ids: [parseUserId(form.approverUserId)],
            exclusive: false,
          },
        ],
      });
      setNotice("Odoo approval rule deployed.");
      await refresh();
    } catch (err) {
      setErrorContext("deploy");
      setError(err instanceof Error ? err.message : "Deploy failed");
    } finally {
      setBusy(false);
    }
  }

  async function simulateCheck(ruleId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.checkApprovalAction(
        connectionId,
        ruleId,
        parseRecordId(form.testRecordId),
        parseUserId(form.approverUserId),
      );
      setNotice(res.allowed ? res.message : `Blocked: ${res.message}`);
      await refresh();
    } catch (err) {
      setErrorContext("check");
      setError(err instanceof Error ? err.message : "Check failed");
    } finally {
      setBusy(false);
    }
  }

  async function approveEntry(entryId: string, approve: boolean) {
    setBusy(true);
    setError(null);
    try {
      await api.approveApprovalEntry(connectionId, entryId, {
        actor_user_id: parseUserId(form.approverUserId),
        approve,
      });
      setNotice(approve ? "Entry approved." : "Entry rejected.");
      await refresh();
    } catch (err) {
      setErrorContext("resolve");
      setError(err instanceof Error ? err.message : "Resolve failed");
    } finally {
      setBusy(false);
    }
  }

  const buttonsPane = (
    <>
      <p className="ap-lead">
        Studio-style button gating. Uses Community rules by default; Enterprise Studio when
        detected.
      </p>

      {error ? (
        <div className="mt-4">
          <ApprovalsStateGuide
            tone="danger"
            live
            testId="approvals-error"
            guide={{
              ...approvalsErrorGuide(errorContext),
              why: error,
            }}
            actions={
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setError(null);
                  setListHydrated(false);
                  void refresh()
                    .catch((err: Error) => {
                      setErrorContext("load");
                      setError(err.message);
                    })
                    .finally(() => setListHydrated(true));
                }}
              >
                Retry
              </Button>
            }
          />
        </div>
      ) : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4" testId="approvals-notice">
          {notice}
        </Callout>
      ) : null}

      <ApprovalRuleComposer
        form={form}
        buttons={buttons}
        busy={busy}
        onChange={(next) => setForm((f) => ({ ...f, ...next }))}
        onDiscover={() => void loadButtons()}
        onDeploy={(e) => void onDeploy(e)}
      />

      <ApprovalRulesList
        rules={rules}
        loading={!listHydrated}
        busy={busy}
        query={listQuery}
        testRecordId={form.testRecordId}
        onQueryChange={setListQuery}
        onTestRecordIdChange={(value) => setForm((f) => ({ ...f, testRecordId: value }))}
        onSimulate={(ruleId) => void simulateCheck(ruleId)}
        onOpenComposer={() =>
          document.getElementById("approval-new-rule")?.scrollIntoView({ behavior: "smooth" })
        }
      />

      <ApprovalEntriesList
        entries={entries}
        loading={!listHydrated}
        busy={busy}
        onRefresh={() => void refresh()}
        onResolve={(entryId, approve) => void approveEntry(entryId, approve)}
      />
    </>
  );

  return (
    <OperateStudioChrome
      testIdPrefix="approvals"
      pageTestId="approvals-page"
      kicker={connection?.name ?? connectionId}
      title={PAGE_TITLE}
      subtitle={PAGE_DESCRIPTION}
      badge={approvalsSessionBadge(gate)}
      honesty={approvalsHonestyGuide(gate)}
      sanitize={sanitizeApprovalsCopy}
      shellClassName="approvals-operate"
      className="p-4 sm:p-6"
      titleActions={
        <Link href="/approvals" data-testid="approvals-inbox-link" className="text-xs text-[var(--op-chrome-muted)] underline-offset-2 hover:underline">
          Open Approval inbox
        </Link>
      }
    >
      <p className="ap-inbox-note">{INBOX_HINT}</p>
      {/* legacy test id: honesty lives in the studio bar */}
      <span className="sr-only" data-testid="approvals-honesty">
        {engineChipLabel(gate)} · {engineHint(gate)}
      </span>
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      <div className="ap-tabs">
        <Tabs
          value={tab}
          onValueChange={(v) => setTab(v as ApprovalsTab)}
          items={[
            { value: "buttons", label: "Button rules", content: buttonsPane },
            {
              value: "processes",
              label: "Approval processes",
              content: (
                <ApprovalProcessesPanel connectionId={connectionId} connection={connection} />
              ),
            },
          ]}
        />
      </div>
    </OperateStudioChrome>
  );
}

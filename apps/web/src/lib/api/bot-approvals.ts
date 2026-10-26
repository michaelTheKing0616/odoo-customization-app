import { request } from "./client";

/** BOT-APPROVAL-TIERS: server-computed plan card. Tier and record count never come from the UI. */
export type BotApprovalStatus =
  "auto" | "pending" | "approved" | "rejected" | "refused";

export type BotApprovalCard = {
  summary: string;
  model: string;
  changes: { field: string; to: string }[];
  records: number;
  risk: string;
  tier: 1 | 2 | 3 | null;
  tier_label: string;
  reasons: string[];
  refusal: string | null;
  undo: { available: boolean; how: string };
  rehearsal: { passed: boolean };
  limits: string[];
};

export type BotApproval = {
  id: string;
  connection_id: string;
  task_id: string;
  risk_class: string;
  n_records: number;
  tier: 1 | 2 | 3 | null;
  status: BotApprovalStatus;
  requested_by: string;
  decided_by: string | null;
  card: BotApprovalCard;
  created_at: string | null;
  decided_at: string | null;
};

const base = (connectionId: string) =>
  `/api/connections/${encodeURIComponent(connectionId)}/bot-approvals`;

export const botApprovalsApi = {
  list: (connectionId: string) =>
    request<{ items: BotApproval[] }>(base(connectionId)),
  get: (connectionId: string, id: string) =>
    request<BotApproval>(`${base(connectionId)}/${encodeURIComponent(id)}`),
  approve: (connectionId: string, id: string) =>
    request<BotApproval>(
      `${base(connectionId)}/${encodeURIComponent(id)}/approve`,
      {
        method: "POST",
      },
    ),
  reject: (connectionId: string, id: string) =>
    request<BotApproval>(
      `${base(connectionId)}/${encodeURIComponent(id)}/reject`,
      {
        method: "POST",
      },
    ),
};

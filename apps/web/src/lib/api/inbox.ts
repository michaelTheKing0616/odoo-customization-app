import { request } from "./client";

export type InboxPlan = {
  plan_hash: string;
  goal: string;
  status: string;
  max_risk: string;
  environment: string;
  expires_at: string;
  sections?: { title: string; body: string }[];
};

export const inboxApi = {
  listInboxPlans: (connectionId: string) =>
    request<{ plans: InboxPlan[] }>(
      `/api/inbox/plans?connection_id=${encodeURIComponent(connectionId)}`,
    ),
};

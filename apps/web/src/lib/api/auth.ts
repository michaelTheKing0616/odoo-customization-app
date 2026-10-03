import { request } from "./client";
import type { AuditLogRow } from "./types-catalog";

export type AuthStatus = {
  auth_mode: string;
  auth_enabled: boolean;
  active_keys: number;
  env_key_configured: boolean;
  bootstrap_available: boolean;
};

export type EntitlementsOut = {
  workspace_id: string;
  plan_id: string;
  subscription_status: string;
  features: Record<string, string>;
  extra_project_slots: number;
  active_projects: number;
  active_project_limit: number | null;
  trial_ends_at: string | null;
  current_period_end: string | null;
};

export type BillingPlanRow = {
  id: string;
  display_name: string;
  features: Record<string, string>;
  monthly_usd: number | null;
  extra_slot_monthly_usd: number | null;
};

export type BillingPlansCatalog = {
  tier_order: string[];
  display_features: Array<{ key: string; label: string }>;
  project_pass: { display_name: string; one_time_usd: number };
  plans: BillingPlanRow[];
};

export type AccountSession = {
  user: {
    id: string;
    email: string;
    email_verified: boolean;
    totp_enabled: boolean;
    is_superadmin: boolean;
  };
  workspace: {
    id: string;
    name: string;
    slug: string;
    plan: string;
    role: string;
  };
};

export type ApiKeyRow = {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
};

export const authApi = {
  authStatus: () => request<AuthStatus>("/api/auth/status"),
  accountSignup: (body: { email: string; password: string; workspace_name?: string }) =>
    request<{ message: string; user_id: string; workspace_id: string }>("/api/accounts/signup", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accountLogin: (body: { email: string; password: string; totp_code?: string }) =>
    request<AccountSession>("/api/accounts/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accountLogout: () => request<void>("/api/accounts/logout", { method: "POST" }),
  accountMe: () => request<AccountSession>("/api/accounts/me"),
  accountVerifyEmail: (token: string) =>
    request<{ message: string }>("/api/accounts/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  accountRequestPasswordReset: (email: string) =>
    request<void>("/api/accounts/request-password-reset", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  accountResetPassword: (token: string, password: string) =>
    request<{ message: string }>("/api/accounts/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),
  accountOAuthProviders: () => request<{ providers: string[] }>("/api/accounts/oauth/providers"),
  accountOAuthComplete2FA: (body: { token: string; totp_code: string }) =>
    request<AccountSession>("/api/accounts/oauth/complete-2fa", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accountOAuthIdentities: () =>
    request<Array<{ provider: string; email: string | null; created_at: string }>>(
      "/api/accounts/oauth/identities",
    ),
  accountOAuthUnlink: (provider: string) =>
    request<void>(`/api/accounts/oauth/${encodeURIComponent(provider)}`, { method: "DELETE" }),
  billingEntitlements: () => request<EntitlementsOut>("/api/billing/entitlements"),
  billingPlans: () => request<BillingPlansCatalog>("/api/billing/plans"),
  billingPlanDiff: (fromPlan: string, toPlan = "free_solo") =>
    request<{ from_plan: string; to_plan: string; lost_features: Array<{ feature_key: string; from: string; to: string }> }>(
      `/api/billing/plan-diff?from_plan=${encodeURIComponent(fromPlan)}&to_plan=${encodeURIComponent(toPlan)}`,
    ),
  stripeCheckout: (body: {
    plan_id: string;
    seat_quantity: number;
    success_url: string;
    cancel_url: string;
  }) =>
    request<{ checkout_url: string; session_id: string; mode: string }>("/api/billing/checkout/stripe", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  stripeExtraSlotsCheckout: (body: {
    slot_quantity: number;
    success_url: string;
    cancel_url: string;
  }) =>
    request<{ checkout_url: string; session_id: string; mode: string }>(
      "/api/billing/checkout/stripe/extra-slots",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  stripePortal: () => request<{ portal_url: string }>("/api/billing/portal/stripe", { method: "POST" }),
  bootstrapApiKey: () =>
    request<{ api_key: string; key_id: string; name: string; note: string }>(
      "/api/auth/bootstrap",
      { method: "POST" },
    ),
  listApiKeys: () => request<ApiKeyRow[]>("/api/auth/keys"),
  createApiKey: (name: string) =>
    request<{ id: string; name: string; key_prefix: string; api_key: string; note: string }>(
      "/api/auth/keys",
      { method: "POST", body: JSON.stringify({ name }) },
    ),
  revokeApiKey: (keyId: string) =>
    request<void>(`/api/auth/keys/${keyId}`, { method: "DELETE" }),
  listAuditLogs: (limit = 100) =>
    request<AuditLogRow[]>(`/api/audit/logs?limit=${limit}`),
};

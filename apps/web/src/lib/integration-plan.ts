/**
 * App Studio integration plan (API `integration_plan`): which apps a brief can
 * use, which were deferred or left out, and which pieces need the Option A lane.
 * Read from the create/generate response or the persisted `integration_plan` turn.
 */
import type { PreviewDeferredIntegration } from "@/components/odoo-preview/OdooFormView";
import type { StudioTurn } from "@/lib/studio-session";

export type IntegrationStatus = "available" | "deferred" | "left_out" | "unchecked";

export type IntegrationItem = {
  module: string;
  app_label: string;
  model: string;
  status: IntegrationStatus;
  note: string;
};

export type PythonPiece = {
  key: string;
  label: string;
  delivery_lane?: string;
  online_blocked?: "true" | "false" | boolean;
  lane_note?: string;
};

export type IntegrationPlan = {
  primary_module?: string | null;
  edition?: string;
  hosting?: string;
  core_built?: boolean;
  integrations: IntegrationItem[];
  left_out?: string[];
  omitted_models?: string[];
  python_pieces?: PythonPiece[];
  summary?: string;
};

function asPlan(raw: unknown): IntegrationPlan | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Partial<IntegrationPlan>;
  const integrations = Array.isArray(obj.integrations) ? obj.integrations : [];
  const pieces = Array.isArray(obj.python_pieces) ? obj.python_pieces : [];
  if (integrations.length === 0 && pieces.length === 0) return null;
  return { ...obj, integrations, python_pieces: pieces } as IntegrationPlan;
}

export function integrationPlanFromSession(
  session: { integration_plan?: unknown; conversation?: StudioTurn[] } | null | undefined,
): IntegrationPlan | null {
  if (!session) return null;
  const direct = asPlan(session.integration_plan);
  if (direct) return direct;
  const turns = session.conversation || [];
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    const turn = turns[i];
    if (turn.kind === "integration_plan") {
      const plan = asPlan(turn.metadata?.integration_plan);
      if (plan) return plan;
    }
  }
  return null;
}

export function pythonBlockedOnHost(piece: PythonPiece): boolean {
  return piece.online_blocked === true || piece.online_blocked === "true";
}

/** Ghost rows for the form preview: left out and deferred apps. */
export function deferredIntegrationsOf(plan: IntegrationPlan | null): PreviewDeferredIntegration[] {
  if (!plan) return [];
  return plan.integrations
    .filter((i) => i.status === "left_out" || i.status === "deferred")
    .map((i) => ({
      label: i.app_label,
      status: i.status === "left_out" ? ("left_out" as const) : ("deferred" as const),
      note: i.note,
    }));
}

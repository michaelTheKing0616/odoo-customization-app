/** Carry brief + Diagnosis/Contract + delivery_lane stamps across Build surfaces. */

import type { BuildMode, BuildSpinePayload } from "./build-spine";
import {
  briefTextForJobAutopilot,
  jobAutopilotBriefStorageKey,
  readJobAutopilotBrief,
  stashJobAutopilotBrief,
} from "./job-brief-handoff";

export function buildSpineHandoffKey(connectionId: string): string {
  return `ingenium-build-spine:${connectionId}`;
}

export type BuildSpineHandoff = {
  version: 1;
  brief: string;
  prompt: string;
  build_mode?: BuildMode | null;
  capability?: string | null;
  grain?: string | null;
  delivery_lane?: string | null;
  artifact_kind?: string | null;
  prove_status?: string | null;
  gold_artifact_id?: string | null;
  diagnosis?: Record<string, unknown> | null;
  contract?: Record<string, unknown> | null;
  generation_ir?: Record<string, unknown> | null;
  updated_at?: string;
};

export function handoffFromPayload(payload: BuildSpinePayload): BuildSpineHandoff {
  return {
    version: 1,
    brief: payload.brief || payload.prompt || "",
    prompt: payload.prompt || payload.brief || "",
    build_mode: payload.build_mode,
    capability: payload.capability,
    grain: payload.grain,
    delivery_lane: payload.delivery_lane,
    artifact_kind: payload.artifact_kind,
    prove_status: payload.prove_status,
    gold_artifact_id: payload.gold_artifact_id,
    diagnosis: payload.diagnosis || null,
    contract: payload.contract || null,
    updated_at: new Date().toISOString(),
  };
}

export function stashBuildSpineHandoff(connectionId: string, handoff: BuildSpineHandoff): void {
  if (!connectionId) return;
  const brief = (handoff.brief || handoff.prompt || "").trim();
  if (!brief && !handoff.delivery_lane) return;
  try {
    const payload: BuildSpineHandoff = {
      ...handoff,
      version: 1,
      brief,
      prompt: (handoff.prompt || brief).trim(),
      updated_at: new Date().toISOString(),
    };
    sessionStorage.setItem(buildSpineHandoffKey(connectionId), JSON.stringify(payload));
    // Keep Job Autopilot brief key in sync so existing readers still work.
    if (brief) stashJobAutopilotBrief(connectionId, brief);
  } catch {
    /* private mode */
  }
}

export function readBuildSpineHandoff(connectionId: string): BuildSpineHandoff | null {
  if (!connectionId) return null;
  try {
    const raw = sessionStorage.getItem(buildSpineHandoffKey(connectionId));
    if (raw) {
      const parsed = JSON.parse(raw) as BuildSpineHandoff;
      if (parsed && typeof parsed === "object") {
        return parsed;
      }
    }
  } catch {
    /* ignore */
  }
  // Fallback: brief-only stash from older Draft → Job path.
  const brief = readJobAutopilotBrief(connectionId);
  if (!brief) return null;
  return {
    version: 1,
    brief,
    prompt: brief,
  };
}

export function clearBuildSpineHandoff(connectionId: string): void {
  try {
    sessionStorage.removeItem(buildSpineHandoffKey(connectionId));
    sessionStorage.removeItem(jobAutopilotBriefStorageKey(connectionId));
  } catch {
    /* ignore */
  }
}

export function handoffFromDraft(
  draft: Record<string, unknown> | null | undefined,
  fallbackPrompt = "",
): BuildSpineHandoff {
  const brief = briefTextForJobAutopilot(draft, fallbackPrompt);
  const ir =
    draft && typeof draft._generation_engine === "object" && draft._generation_engine
      ? (draft._generation_engine as Record<string, unknown>)
      : null;
  const contract =
    draft && typeof draft._studio_contract === "object" && draft._studio_contract
      ? (draft._studio_contract as Record<string, unknown>)
      : null;
  return {
    version: 1,
    brief,
    prompt: brief,
    capability: ir && typeof ir.capability === "string" ? ir.capability : null,
    grain:
      (ir && typeof ir.grain === "string" && ir.grain) ||
      (contract && typeof contract.grain === "string" && contract.grain) ||
      (typeof draft?.grain === "string" ? draft.grain : null),
    delivery_lane: ir && typeof ir.delivery_lane === "string" ? ir.delivery_lane : null,
    artifact_kind: ir && typeof ir.artifact_kind === "string" ? ir.artifact_kind : null,
    prove_status: ir && typeof ir.prove_status === "string" ? ir.prove_status : null,
    gold_artifact_id:
      ir && typeof ir.gold_artifact_id === "string" ? ir.gold_artifact_id : null,
    diagnosis: ir,
    contract,
    generation_ir: ir,
  };
}

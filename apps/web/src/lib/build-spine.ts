/** P2 Build spine — mode chips + surface hrefs (ingenium). */

export type BuildMode =
  | "prefer_pack"
  | "residual_app"
  | "option_a"
  | "stock_autopilot"
  | "report_layout"
  | "connector";

export type BuildSpineChip = {
  id: BuildMode;
  label: string;
  blurb: string;
  surface: string;
  href: string;
  active: boolean;
};

export type BuildSpinePayload = {
  version: number;
  prompt: string;
  brief: string;
  build_mode: BuildMode;
  chips: BuildSpineChip[];
  capability?: string | null;
  grain?: string | null;
  gold_artifact_id?: string | null;
  delivery_lane?: string | null;
  artifact_kind?: string | null;
  prove_status?: string | null;
  delivery_lane_copy?: string | null;
  artifact_kind_copy?: string | null;
  promote_human?: boolean;
  completeness_is_not_cert?: boolean;
  diagnosis?: Record<string, unknown>;
  contract?: Record<string, unknown>;
  surfaces?: Record<string, string>;
  honesty?: string;
  atlas_class?: string | null;
  recipe_id?: string | null;
  risk?: string | null;
  atlas_route?: string | null;
};

export const BUILD_MODE_META: Record<
  BuildMode,
  { label: string; surface: "studio" | "wizard" | "job" | "designer"; blurb: string }
> = {
  prefer_pack: {
    label: "Field pack",
    surface: "designer",
    blurb: "Adds fields on an existing form — not a new Apps tile.",
  },
  residual_app: {
    label: "Custom app",
    surface: "studio",
    blurb: "New custom app — keeps its own identity; not reshaped into a field pack.",
  },
  option_a: {
    label: "Custom code",
    surface: "studio",
    blurb: "Installable module — prove on a test copy, then publish.",
  },
  stock_autopilot: {
    label: "Built-in Autopilot",
    surface: "job",
    blurb: "Job Autopilot using built-in apps first — no custom code invent.",
  },
  report_layout: {
    label: "Report layout",
    surface: "studio",
    blurb: "QWeb / document layout — not a Contacts field-pack delivery.",
  },
  connector: {
    label: "Connector",
    surface: "studio",
    blurb: "FX / HTTP provider — gold custom code or an external connector path.",
  },
};

export function hrefForBuildMode(connectionId: string, mode: BuildMode): string {
  const surface = BUILD_MODE_META[mode].surface;
  const slug =
    surface === "designer"
      ? "designer"
      : surface === "job"
        ? "job"
        : surface === "wizard"
          ? "wizard"
          : "studio";
  return `/connections/${connectionId}/${slug}`;
}

/** Client-side mode hint when API payload is not yet loaded. */
export function resolveBuildModeLocal(input: {
  capability?: string | null;
  grain?: string | null;
  artifact_kind?: string | null;
  delivery_lane?: string | null;
  gold_artifact_id?: string | null;
}): BuildMode {
  const kind = (input.artifact_kind || "").trim();
  const cap = (input.capability || "").trim();
  const grain = (input.grain || "").trim();
  const gold = (input.gold_artifact_id || "").trim();
  const lane = (input.delivery_lane || "").trim();
  if (kind === "report_layout") return "report_layout";
  if (kind === "external_connector" || gold === "currency_rate_cbn" || lane === "external_connector") {
    return "connector";
  }
  if (cap === "option_a_authored" || cap === "option_a_standalone" || kind === "option_a_module") {
    return "option_a";
  }
  if (cap === "stock_reuse" || kind === "stock_config") return "stock_autopilot";
  if (grain === "field_pack" || kind === "field_pack") return "prefer_pack";
  if (grain === "full_app" || kind === "full_app" || cap === "residual_app") return "residual_app";
  return "residual_app";
}

export function defaultChips(connectionId: string, active: BuildMode): BuildSpineChip[] {
  const ids: BuildMode[] = [
    "prefer_pack",
    "residual_app",
    "option_a",
    "stock_autopilot",
    "report_layout",
    "connector",
  ];
  const show =
    active === "report_layout" || active === "connector"
      ? (["prefer_pack", "residual_app", "option_a", "stock_autopilot", active] as BuildMode[])
      : (["prefer_pack", "residual_app", "option_a", "stock_autopilot"] as BuildMode[]);
  const ordered = [active, ...show, ...ids].filter(
    (m, i, arr) => arr.indexOf(m) === i,
  ) as BuildMode[];
  return ordered.map((id) => ({
    id,
    label: BUILD_MODE_META[id].label,
    blurb: BUILD_MODE_META[id].blurb,
    surface: BUILD_MODE_META[id].surface,
    href: hrefForBuildMode(connectionId, id),
    active: id === active,
  }));
}

export const BUILD_SPINE_HONESTY =
  "One Build entry — App Studio, Draft Studio, and Job Autopilot share brief + stamps. A complete draft is not the same as certified, and neither means Autopilot-ready. Publishing stays a step you confirm.";

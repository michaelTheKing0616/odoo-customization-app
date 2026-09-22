import { afterEach, describe, expect, it } from "vitest";
import {
  clearBuildSpineHandoff,
  handoffFromDraft,
  readBuildSpineHandoff,
  stashBuildSpineHandoff,
} from "./build-spine-handoff";
import { readJobAutopilotBrief } from "./job-brief-handoff";

describe("build-spine-handoff", () => {
  const id = "conn-spine";

  afterEach(() => {
    clearBuildSpineHandoff(id);
  });

  it("round-trips brief + stamps without re-briefing", () => {
    stashBuildSpineHandoff(id, {
      version: 1,
      brief: "Add markup % on sales with WHT on markup only",
      prompt: "Add markup % on sales with WHT on markup only",
      build_mode: "option_a",
      delivery_lane: "module_sh_or_self",
      artifact_kind: "option_a_module",
      capability: "option_a_authored",
    });
    const got = readBuildSpineHandoff(id);
    expect(got?.brief).toContain("markup");
    expect(got?.delivery_lane).toBe("module_sh_or_self");
    expect(got?.artifact_kind).toBe("option_a_module");
    expect(readJobAutopilotBrief(id)).toContain("markup");
  });

  it("handoffFromDraft reads IR stamps", () => {
    const h = handoffFromDraft({
      _user_prompt: "scrub delivery slip address",
      grain: "full_app",
      _generation_engine: {
        capability: "option_a_authored",
        delivery_lane: "module_sh_or_self",
        artifact_kind: "report_layout",
      },
      _studio_contract: { grain: "full_app", host_model: "stock.picking" },
    });
    expect(h.artifact_kind).toBe("report_layout");
    expect(h.delivery_lane).toBe("module_sh_or_self");
    expect(h.brief).toContain("scrub");
  });
});

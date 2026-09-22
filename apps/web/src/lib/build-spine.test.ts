import { describe, expect, it } from "vitest";
import {
  defaultChips,
  hrefForBuildMode,
  resolveBuildModeLocal,
} from "./build-spine";

describe("build-spine", () => {
  it("resolves Prefer / Option A / report / connector / stock", () => {
    expect(resolveBuildModeLocal({ grain: "field_pack", artifact_kind: "field_pack" })).toBe(
      "prefer_pack",
    );
    expect(
      resolveBuildModeLocal({ capability: "option_a_authored", artifact_kind: "option_a_module" }),
    ).toBe("option_a");
    expect(resolveBuildModeLocal({ artifact_kind: "report_layout" })).toBe("report_layout");
    expect(
      resolveBuildModeLocal({
        gold_artifact_id: "currency_rate_cbn",
        artifact_kind: "external_connector",
      }),
    ).toBe("connector");
    expect(resolveBuildModeLocal({ capability: "stock_reuse" })).toBe("stock_autopilot");
    expect(resolveBuildModeLocal({ capability: "residual_app", grain: "full_app" })).toBe(
      "residual_app",
    );
  });

  it("builds hrefs and default chips with active first", () => {
    expect(hrefForBuildMode("c1", "prefer_pack")).toBe("/connections/c1/designer");
    expect(hrefForBuildMode("c1", "stock_autopilot")).toBe("/connections/c1/job");
    const chips = defaultChips("c1", "option_a");
    expect(chips[0].id).toBe("option_a");
    expect(chips[0].active).toBe(true);
    expect(chips.some((c) => c.id === "prefer_pack")).toBe(true);
  });
});

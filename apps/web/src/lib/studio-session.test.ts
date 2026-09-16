import { describe, expect, it } from "vitest";
import {
  invertRefineText,
  refineHistoryItems,
  studioAppIsLiveOnOdoo,
  studioApplyMenuTarget,
  studioPhaseFromSession,
  undoInstructionForRefine,
  type StudioSession,
} from "./studio-session";

const base: StudioSession = {
  id: "s1",
  status: "review",
  prompt_original: "tickets",
  prompt_resolved: "tickets",
};

describe("studioApplyMenuTarget", () => {
  it("reads stamped apply ids from the artifact", () => {
    const target = studioApplyMenuTarget({
      ...base,
      artifact: { _studio_apply: { root_menu_id: 42, open_action_id: 9 } },
    });
    expect(target).toEqual({ rootMenuId: 42, openActionId: 9, hostModel: null, applied: true });
  });

  it("marks applied when stamp exists without a root menu", () => {
    expect(
      studioApplyMenuTarget({
        ...base,
        artifact: { _studio_apply: { root_menu_id: null, open_action_id: null } },
      }).applied,
    ).toBe(true);
  });

  it("falls back to apply-turn metadata", () => {
    const target = studioApplyMenuTarget({
      ...base,
      conversation: [
        {
          role: "system",
          kind: "apply",
          content: "Applied",
          metadata: { root_menu_id: 77, open_action_id: 3 },
        },
      ],
    });
    expect(target).toEqual({ rootMenuId: 77, openActionId: 3, hostModel: null, applied: true });
  });
});

describe("studioAppIsLiveOnOdoo", () => {
  it("is false until Apply stamps a root menu or inherit host", () => {
    expect(studioAppIsLiveOnOdoo(base)).toBe(false);
    expect(
      studioAppIsLiveOnOdoo({
        ...base,
        status: "delivered",
        artifact: { models: [{ model: "x_ticket" }] },
      }),
    ).toBe(false);
    expect(
      studioAppIsLiveOnOdoo({
        ...base,
        artifact: { _studio_apply: { root_menu_id: 42 } },
      }),
    ).toBe(true);
  });

  it("is true for a field pack apply with no new app tile", () => {
    expect(
      studioAppIsLiveOnOdoo({
        ...base,
        artifact: {
          _studio_apply: {
            root_menu_id: null,
            open_action_id: 88,
            host_model: "account.move",
            applied: true,
          },
        },
      }),
    ).toBe(true);
  });

  it("enables Open in Odoo from the inherit host when Apply left no root menu", () => {
    expect(
      studioAppIsLiveOnOdoo({
        ...base,
        status: "delivered",
        artifact: {
          models: [{ model: "account.move", mode: "inherit" }],
          _studio_apply: { root_menu_id: null, open_action_id: null },
        },
      }),
    ).toBe(true);
  });

  it("still opens the stock host when a leftover x_* model sits beside inherit", () => {
    const target = studioApplyMenuTarget({
      ...base,
      status: "delivered",
      artifact: {
        models: [
          { model: "x_invoice_extras" },
          { model: "account.move", mode: "inherit" },
        ],
        _studio_apply: { root_menu_id: null, open_action_id: null },
      },
    });
    expect(target.applied).toBe(true);
    expect(target.hostModel).toBe("account.move");
    expect(
      studioAppIsLiveOnOdoo({
        ...base,
        status: "delivered",
        artifact: {
          models: [
            { model: "x_invoice_extras" },
            { model: "account.move", mode: "inherit" },
          ],
          _studio_apply: { root_menu_id: null, open_action_id: null },
        },
      }),
    ).toBe(true);
  });

  it("treats Option A promote stamp as live on the inherit host", () => {
    expect(
      studioAppIsLiveOnOdoo({
        ...base,
        artifact: {
          models: [{ model: "sale.order", mode: "inherit" }],
          _studio_apply: {
            root_menu_id: null,
            open_action_id: null,
            host_model: "sale.order",
            applied: true,
            via: "option_a_promote",
          },
        },
      }),
    ).toBe(true);
    expect(
      studioApplyMenuTarget({
        ...base,
        artifact: {
          models: [{ model: "sale.order", mode: "inherit" }],
          _studio_apply: {
            host_model: "sale.order",
            applied: true,
            via: "option_a_promote",
          },
        },
      }).hostModel,
    ).toBe("sale.order");
  });

  it("ignores leftover menu_id after Option A promote (Discuss trap)", () => {
    const target = studioApplyMenuTarget({
      ...base,
      artifact: {
        models: [{ model: "sale.order", mode: "inherit" }],
        _studio_apply: {
          root_menu_id: 79,
          open_action_id: 334,
          host_model: "sale.order",
          applied: true,
          via: "option_a_promote",
        },
      },
    });
    expect(target.rootMenuId).toBeNull();
    expect(target.openActionId).toBe(334);
    expect(target.hostModel).toBe("sale.order");
  });
});

describe("studioPhaseFromSession", () => {
  it("keeps delivered sessions on the review canvas", () => {
    expect(studioPhaseFromSession({ ...base, status: "delivered", artifact: { models: [] } })).toBe(
      "review",
    );
  });

  it("treats ready as generating so the prompt screen is not blank", () => {
    expect(studioPhaseFromSession({ ...base, status: "ready", artifact: {} })).toBe("generating");
  });
});

describe("refineHistoryItems", () => {
  it("returns user refine phrases newest first with undo instructions", () => {
    expect(
      refineHistoryItems([
        { role: "user", kind: "refine", content: "remove priority", at: "2026-09-03T10:00:00Z" },
        { role: "assistant", kind: "refine_result", content: "Removed priority" },
        { role: "user", kind: "refine", content: "add a due date", at: "2026-09-03T10:01:00Z" },
        { role: "user", kind: "clarify", content: "helpdesk" },
      ]),
    ).toEqual([
      {
        at: "2026-09-03T10:01:00Z",
        content: "add a due date",
        isLatest: true,
        undoInstruction: "oops",
      },
      {
        at: "2026-09-03T10:00:00Z",
        content: "remove priority",
        isLatest: false,
        undoInstruction: "restore priority",
      },
    ]);
  });
});

describe("undoInstructionForRefine", () => {
  it("uses oops for the latest turn and restore text for older removes", () => {
    expect(undoInstructionForRefine("remove the Asset Tag ticket", true)).toBe("oops");
    expect(undoInstructionForRefine("remove the Asset Tag ticket", false)).toBe(
      "restore the Asset Tag ticket",
    );
  });

  it("does not invert an oops/undo utterance", () => {
    expect(undoInstructionForRefine("oops", true)).toBeNull();
    expect(undoInstructionForRefine("undo", false)).toBeNull();
  });
});

describe("invertRefineText", () => {
  it("pairs remove/restore and inverts compound clauses", () => {
    expect(invertRefineText("restore the Asset Tag ticket")).toBe("remove the Asset Tag ticket");
    expect(invertRefineText("add a due date")).toBe("remove a due date");
    expect(invertRefineText("make the Reference field required")).toBe(
      "make the Reference field optional",
    );
    expect(invertRefineText("Remove the Extra and restore the Asset Tag ticket")).toBe(
      "restore the Extra and remove the Asset Tag ticket",
    );
  });
});

import { describe, expect, it } from "vitest";

import { residualFormPreviewFromDraft } from "./draft-form-preview";

/** Wireframe drafts reach apply only through the existing Stage H preview. */
const WIREFRAME_DRAFT = {
  _wireframe: { source: "sketch", stage_h: true },
  _generation_engine: {
    capability: "residual_app",
    form_preview: {
      type: "form",
      model: "x_visitor_log",
      title: "Visitor Log",
      groups: [
        {
          id: "details",
          string: "Details",
          columns: 1,
          fields: [
            { id: "x_visitor_name", name: "x_visitor_name", string: "Visitor name", ttype: "char" },
          ],
        },
      ],
    },
  },
};

describe("wireframe Stage H", () => {
  it("reads the header-form preview and rejects a draft without one", () => {
    const preview = residualFormPreviewFromDraft(WIREFRAME_DRAFT);
    expect(preview?.model).toBe("x_visitor_log");
    expect(preview?.groups[0].fields[0].name).toBe("x_visitor_name");
    expect(residualFormPreviewFromDraft({ _wireframe: { source: "sketch", stage_h: false } })).toBeNull();
  });
});

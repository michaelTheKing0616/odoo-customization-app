/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OverlayEditor } from "@/components/designer/OverlayEditor";
import type { FieldRow } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    overlayPreview: vi.fn(async () => ({
      xpath_arch:
        '<data><xpath expr="//field[@name=\'email\']" position="attributes"><attribute name="invisible">1</attribute></xpath></data>',
      issues: [],
    })),
    applyOverlayOp: vi.fn(async () => ({
      xpath_arch: "<data/>",
      issues: [],
      view_id: 1,
      snapshot_id: "snap",
    })),
    getPrimaryView: vi.fn(),
    resolveFieldNode: vi.fn(),
  },
}));

const FIELDS: FieldRow[] = [
  {
    id: 1,
    name: "email",
    field_description: "Email",
    ttype: "char",
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  },
];

describe("OverlayEditor", () => {
  afterEach(() => cleanup());

  it("shows xpath peek for harness selection override", async () => {
    render(
      <OverlayEditor
        iframeRef={{ current: null }}
        connectionId="conn"
        model="res.partner"
        viewType="form"
        fields={FIELDS}
        selectionOverride={{ fieldName: "email", xpath: "//field[@name='email']" }}
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getByTestId("overlay-selected")).toHaveTextContent("email");
    await waitFor(() => {
      expect(screen.getByTestId("overlay-xpath-peek")).toBeInTheDocument();
    });
    expect(screen.getByTestId("overlay-xpath-peek")).toHaveTextContent("invisible");
  });
});

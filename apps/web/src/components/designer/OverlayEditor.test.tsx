/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OverlayEditor } from "@/components/designer/OverlayEditor";
import type { FieldRow } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    overlayPreview: vi.fn(async (_id: string, body: { operation?: string }) => {
      if (body.operation === "add_page") {
        return {
          xpath_arch:
            '<data><xpath expr="//notebook" position="inside"><page name="x_page_new_page" string="New page"><group/></page></xpath></data>',
          issues: [],
          locator_issues: [],
        };
      }
      if (body.operation === "add_group") {
        return {
          xpath_arch:
            '<data><xpath expr="//sheet" position="inside"><group name="x_group_new_group" string="New group"/></xpath></data>',
          issues: [],
          locator_issues: [],
        };
      }
      return {
        xpath_arch:
          '<data><xpath expr="//field[@name=\'email\']" position="attributes"><attribute name="invisible">1</attribute></xpath></data>',
        issues: [],
        locator_issues: [],
      };
    }),
    applyOverlayOp: vi.fn(async () => ({
      xpath_arch: "<data/>",
      issues: [],
      view_id: 1,
      snapshot_id: "snap",
    })),
    getPrimaryView: vi.fn(async () => ({
      arch: '<form><sheet><notebook><page string="Main"><field name="email"/></page></notebook></sheet></form>',
    })),
    resolveFieldNode: vi.fn(),
    resolveStructure: vi.fn(async () => ({
      candidates: [
        {
          xpath: "//notebook",
          tag: "notebook",
          label: "notebook",
          score: 35,
          fragile: false,
          match_count: 1,
        },
        {
          xpath: "//page[@string='Main']",
          tag: "page",
          label: "Main",
          score: 15,
          fragile: true,
          match_count: 1,
        },
      ],
      ambiguous: false,
    })),
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

function renderEditor(
  override?: { fieldName: string; xpath: string } | null,
) {
  return render(
    <OverlayEditor
      iframeRef={{ current: null }}
      connectionId="conn"
      model="res.partner"
      viewType="form"
      fields={FIELDS}
      selectionOverride={override}
      onSaved={vi.fn()}
    />,
  );
}

describe("OverlayEditor", () => {
  afterEach(() => cleanup());

  it("shows xpath peek for harness selection override", async () => {
    renderEditor({ fieldName: "email", xpath: "//field[@name='email']" });
    expect(screen.getByTestId("overlay-selected")).toHaveTextContent("email");
    await waitFor(() => {
      expect(screen.getByTestId("overlay-xpath-peek")).toBeInTheDocument();
    });
    expect(screen.getByTestId("overlay-xpath-peek")).toHaveTextContent("invisible");
    expect(screen.getByTestId("overlay-locator-kind")).toHaveTextContent("Named");
  });

  it("previews add notebook page without a field selection", async () => {
    renderEditor(null);
    fireEvent.change(screen.getByLabelText("Operation"), { target: { value: "add_page" } });
    await waitFor(() => {
      expect(screen.getByTestId("overlay-xpath-peek")).toHaveTextContent("x_page_new_page");
    });
    expect(screen.getByText(/Split, merge, or bulk-reorder groups/)).toBeInTheDocument();
    expect(screen.queryByText(/notebook pages/i)).not.toBeInTheDocument();
  });

  it("previews add group from overlay", async () => {
    renderEditor(null);
    fireEvent.change(screen.getByLabelText("Operation"), { target: { value: "add_group" } });
    await waitFor(() => {
      expect(screen.getByTestId("overlay-xpath-peek")).toHaveTextContent("x_group_new_group");
    });
  });

  it("disables save when a locator error is blocking", async () => {
    const { api } = await import("@/lib/api");
    vi.mocked(api.overlayPreview).mockResolvedValueOnce({
      xpath_arch:
        '<data><xpath expr="//field[@name=\'missing\']" position="attributes"><attribute name="invisible">1</attribute></xpath></data>',
      issues: ["Locator matches no node in the parent view."],
      locator_issues: [
        {
          severity: "error",
          code: "missing_node",
          message: "Locator matches no node in the parent view.",
        },
      ],
    });
    renderEditor({ fieldName: "email", xpath: "//field[@name='email']" });
    await waitFor(() => {
      expect(screen.getByTestId("overlay-xpath-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("overlay-save")).toBeDisabled();
  });
});

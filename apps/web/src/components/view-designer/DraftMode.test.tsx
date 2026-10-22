import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { StudioFormPreview } from "@/components/studio/StudioFormPreview";
import { draftToEngine } from "./draftEngine";
import { viewDesignerHref } from "./OpenInViewDesigner";

afterEach(cleanup);

const draft = {
  type: "form" as const, model: "x_job", title: "Job",
  groups: [{ id: "g1", string: "Main", columns: 2 as const, fields: [
    { id: "f1", name: "x_name", string: "Job name", ttype: "char" },
    { id: "f2", name: "x_done", string: "Done", ttype: "boolean" },
  ] }],
  notebooks: [{ id: "n1", pages: [{ id: "p1", string: "Notes", fields: [{ id: "f3", name: "x_note", string: "Note", ttype: "text" }] }] }],
  statusbar: { field: "x_state", stages: ["New", "Done"] },
};

describe("draft mode", () => {
  it("builds an engine tree with labelled sample values only", () => {
    const { tree, record } = draftToEngine(draft);
    expect(tree.kind).toBe("root");
    expect(tree.children.map((c) => c.tag)).toEqual(["header", "sheet"]);
    expect(record.x_name).toBe("Sample job name");
    expect(record.x_done).toBe(false);
    expect(record.x_state).toBe("New");
  });

  it("renders the draft through the engine canvas, read-only, with the sample label", () => {
    render(<StudioFormPreview preview={draft} highlightedFieldIds={["f1"]} />);
    expect(screen.getByTestId("studio-engine-preview")).toHaveAttribute("data-mode", "draft");
    expect(screen.getByText("Sample values, not real records")).toBeInTheDocument();
    expect(screen.getAllByText("Job name").length).toBeGreaterThan(0);
  });

  it("links to View Designer on the installed screen", () => {
    expect(viewDesignerHref("c 1", "x_job")).toBe("/connections/c%201/view-designer?model=x_job&type=form");
  });
});

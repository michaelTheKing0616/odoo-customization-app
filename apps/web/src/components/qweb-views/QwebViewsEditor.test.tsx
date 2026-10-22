import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QwebViewsEditor } from "./QwebViewsEditor";
import { defaultQwebViewBlocks } from "./qwebViewBlocks";

const fields = [
  {
    id: 1,
    name: "name",
    field_description: "Name",
    ttype: "char",
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  },
  {
    id: 2,
    name: "display_name",
    field_description: "Display Name",
    ttype: "char",
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  },
];

describe("QwebViewsEditor", () => {
  it("gates unsafe source XML on save", async () => {
    const onError = vi.fn();
    const onSave = vi.fn();
    render(
      <QwebViewsEditor
        view={{
          id: 1,
          name: "Doc",
          key: "x_mod.doc",
          model: "res.partner",
        }}
        arch="<script>bad</script>"
        blocks={defaultQwebViewBlocks()}
        fields={fields}
        editorTab="source"
        strategy="overwrite"
        inheritXpath="//div[hasclass('page')]"
        inheritPosition="inside"
        existingTCalls={[]}
        canMutate
        onArchChange={() => undefined}
        onBlocksChange={() => undefined}
        onEditorTabChange={() => undefined}
        onStrategyChange={() => undefined}
        onInheritXpathChange={() => undefined}
        onInheritPositionChange={() => undefined}
        onSave={onSave}
        onError={onError}
      />,
    );
    fireEvent.click(screen.getByTestId("qweb-views-save"));
    expect(onError).toHaveBeenCalled();
    expect(String(onError.mock.calls[0][0])).toMatch(/script/i);
    expect(onSave).not.toHaveBeenCalled();
  });

  it("shows empty desk when no view selected", () => {
    render(
      <QwebViewsEditor
        view={null}
        arch=""
        blocks={[]}
        fields={[]}
        editorTab="visual"
        strategy="inherit"
        inheritXpath="//div[hasclass('page')]"
        inheritPosition="inside"
        existingTCalls={[]}
        onArchChange={() => undefined}
        onBlocksChange={() => undefined}
        onEditorTabChange={() => undefined}
        onStrategyChange={() => undefined}
        onInheritXpathChange={() => undefined}
        onInheritPositionChange={() => undefined}
        onSave={() => undefined}
        onError={() => undefined}
      />,
    );
    expect(screen.getByTestId("qweb-views-editor-empty")).toBeTruthy();
  });
});

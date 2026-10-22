import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MailTemplatesEditor } from "./MailTemplatesEditor";
import { defaultMailBlocks } from "./mailBodyBlocks";

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
    name: "email",
    field_description: "Email",
    ttype: "char",
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  },
  {
    id: 3,
    name: "display_name",
    field_description: "Display Name",
    ttype: "char",
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  },
];

describe("MailTemplatesEditor", () => {
  it("gates unsafe source HTML on save", async () => {
    const onError = vi.fn();
    const onSave = vi.fn();
    render(
      <MailTemplatesEditor
        template={{
          id: 1,
          name: "T",
          model: "res.partner",
          subject: "Hi",
          body_html: "<p>ok</p>",
        }}
        subject="Hi"
        emailTo="{{ object.email }}"
        bodyHtml="<script>bad</script>"
        blocks={defaultMailBlocks()}
        fields={fields}
        editorTab="source"
        canMutate
        onSubjectChange={() => undefined}
        onEmailToChange={() => undefined}
        onBodyHtmlChange={() => undefined}
        onBlocksChange={() => undefined}
        onEditorTabChange={() => undefined}
        onSave={onSave}
        onError={onError}
      />,
    );
    fireEvent.click(screen.getByTestId("mail-templates-save"));
    expect(onError).toHaveBeenCalled();
    expect(String(onError.mock.calls[0][0])).toMatch(/script/i);
    expect(onSave).not.toHaveBeenCalled();
  });

  it("renders paper blocks for visual mode", () => {
    render(
      <MailTemplatesEditor
        template={{
          id: 2,
          name: "T",
          model: "res.partner",
          subject: "Hello",
          body_html: "<p>x</p>",
        }}
        subject="Hello"
        emailTo="{{ object.email }}"
        bodyHtml="<p>x</p>"
        blocks={defaultMailBlocks("Welcome")}
        fields={fields}
        editorTab="visual"
        canMutate
        onSubjectChange={() => undefined}
        onEmailToChange={() => undefined}
        onBodyHtmlChange={() => undefined}
        onBlocksChange={() => undefined}
        onEditorTabChange={() => undefined}
        onSave={async () => undefined}
        onError={() => undefined}
      />,
    );
    expect(screen.getByTestId("mail-body-blocks")).toBeTruthy();
    expect(screen.getByText("Welcome")).toBeTruthy();
  });
});

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MailPaperPreview } from "./MailPaperPreview";

describe("MailPaperPreview", () => {
  it("renders subject and sanitized body chips", () => {
    render(
      <MailPaperPreview
        subject="Hello"
        emailTo="{{ object.email }}"
        bodyHtml={'<p>Hi {{ object.name }}</p><script>bad</script>'}
      />,
    );
    expect(screen.getByText("Hello")).toBeTruthy();
    expect(screen.getByTestId("mail-paper-body").innerHTML).toMatch(/mail-ph/);
    expect(screen.getByTestId("mail-paper-body").innerHTML).not.toMatch(/<script/i);
  });
});

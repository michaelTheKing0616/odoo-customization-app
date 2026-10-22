import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ReviewRefineLayout } from "./ReviewRefineLayout";

function renderLayout() {
  return render(
    <ReviewRefineLayout
      preview={<div data-testid="preview">Form</div>}
      chat={<div data-testid="thread">Thread</div>}
      chatInput={<textarea data-testid="composer" defaultValue="draft text" />}
    />,
  );
}

afterEach(cleanup);

describe("ReviewRefineLayout", () => {
  it("starts open so server and client markup match", () => {
    renderLayout();
    const layout = screen.getByTestId("studio-review-layout");
    expect(layout.dataset.chat).toBe("open");
    expect(layout.className).not.toMatch(/is-chat-collapsed/);
    const toggle = screen.getByTestId("studio-refine-toggle");
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(toggle.getAttribute("aria-label")).toBe("Hide refine panel");
  });

  it("folds Refine to an icon rail and back without losing the draft", () => {
    renderLayout();
    const toggle = screen.getByTestId("studio-refine-toggle");
    fireEvent.click(toggle);
    const layout = screen.getByTestId("studio-review-layout");
    expect(layout.className).toMatch(/is-chat-collapsed/);
    expect(layout.dataset.chat).toBe("collapsed");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(toggle.getAttribute("aria-label")).toBe("Show refine panel");
    // Chat stays mounted (CSS hides it), so the composer keeps its text.
    expect((screen.getByTestId("composer") as HTMLTextAreaElement).value).toBe("draft text");
    fireEvent.click(toggle);
    expect(layout.dataset.chat).toBe("open");
    expect(screen.getByTestId("preview")).toBeTruthy();
  });
});

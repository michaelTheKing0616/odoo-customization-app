/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ExpertCautionFlags } from "./ExpertCautionFlags";

afterEach(() => cleanup());

describe("ExpertCautionFlags", () => {
  it("elevates access and protected flags with operator copy", () => {
    render(<ExpertCautionFlags flags={["access", "protected_:account.move"]} />);
    expect(screen.getByTestId("expert-caution-flags").textContent).toMatch(/Access \/ ACL/);
    expect(screen.getByTestId("expert-caution-flags").textContent).toMatch(/Protected: account.move/);
    expect(screen.getByTestId("expert-caution-flags").textContent).toMatch(/ir.model.access/);
  });

  it("renders nothing for empty flags", () => {
    const { container } = render(<ExpertCautionFlags flags={[]} />);
    expect(container.textContent).toBe("");
  });
});

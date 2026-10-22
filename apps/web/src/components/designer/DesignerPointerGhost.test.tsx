import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import {
  DesignerPointerGhost,
  GHOST_OFFSET_X,
  GHOST_OFFSET_Y,
  ghostTransform,
  useDesignerPointerGhost,
} from "./DesignerPointerGhost";

afterEach(() => cleanup());

function Row({ dragging }: { dragging: boolean }) {
  const track = useDesignerPointerGhost();
  return (
    <div data-testid="row" data-dragging={dragging ? "true" : undefined} onPointerMove={track}>
      <DesignerPointerGhost label="Customer" name="x_partner_id" />
    </div>
  );
}

describe("DesignerPointerGhost", () => {
  it("positions with a rounded translate3d transform", () => {
    expect(ghostTransform(100.4, 50.6)).toBe(
      `translate3d(${100 + GHOST_OFFSET_X}px, ${51 + GHOST_OFFSET_Y}px, 0)`,
    );
  });

  it("only follows the pointer while the row is dragging", () => {
    const { getByTestId, rerender, container } = render(<Row dragging={false} />);
    const ghost = container.querySelector<HTMLElement>("[data-designer-ghost]")!;
    expect(ghost).toHaveAttribute("aria-hidden");
    fireEvent.pointerMove(getByTestId("row"), { clientX: 10, clientY: 20 });
    expect(ghost.style.transform).toBe("");

    rerender(<Row dragging />);
    fireEvent.pointerMove(getByTestId("row"), { clientX: 10, clientY: 20 });
    expect(ghost.style.transform).toContain("translate3d(");
    expect(ghost).toHaveAttribute("data-positioned", "true");
  });

  it("shows the technical name only when it differs from the label", () => {
    const { container, rerender } = render(<DesignerPointerGhost label="Customer" name="x_partner_id" />);
    expect(container.textContent).toBe("Customerx_partner_id");
    rerender(<DesignerPointerGhost label="x_name" name="x_name" />);
    expect(container.textContent).toBe("x_name");
  });
});

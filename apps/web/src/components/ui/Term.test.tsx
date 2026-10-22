import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Term } from "./Term";
import { lookupTerm } from "@/lib/terms";
import { playSound, soundEnabled } from "@/lib/sound";

describe("Term", () => {
  it("shows the plain word with a hover trigger", () => {
    render(<Term tech="res.partner" />);
    expect(screen.getByTestId("term-res.partner")).toHaveTextContent("Contact");
  });
  it("falls back to plain text for unknown names", () => {
    render(<Term tech="x_custom.thing" />);
    expect(screen.getByText("x_custom.thing")).toBeInTheDocument();
    expect(lookupTerm("x_custom.thing")).toBeUndefined();
  });
  it("sound is off by default and play is a no-op", () => {
    expect(soundEnabled()).toBe(false);
    expect(() => playSound("lock-in")).not.toThrow();
  });
});

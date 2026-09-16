/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BrandMark } from "./BrandMark";

afterEach(() => cleanup());

vi.mock("next/image", () => ({
  default: (props: { alt: string; src: string; "data-testid"?: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img alt={props.alt} src={props.src} data-testid={props["data-testid"]} />
  ),
}));

vi.mock("@/components/theme/ThemeProvider", () => ({
  useThemeOptional: () => ({
    theme: "light",
    resolved: "light",
    setTheme: () => {},
    toggle: () => {},
  }),
}));

describe("BrandMark", () => {
  it("uses mono mark on light theme", () => {
    render(<BrandMark />);
    expect(screen.getByTestId("brand-wordmark")).toHaveTextContent("ingenium");
    expect(screen.getByTestId("brand-mark-image")).toHaveAttribute(
      "src",
      "/brand/ingenium-mark-mono.png",
    );
  });

  it("can force color variant", () => {
    render(<BrandMark variant="color" />);
    expect(screen.getByTestId("brand-mark-image")).toHaveAttribute(
      "src",
      "/brand/ingenium-mark.png",
    );
  });
});

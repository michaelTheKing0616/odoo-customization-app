/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BrandMark } from "./BrandMark";

afterEach(() => cleanup());

vi.mock("next/image", () => ({
  default: (props: {
    alt: string;
    src: string;
    className?: string;
    "data-testid"?: string;
  }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      alt={props.alt}
      src={props.src}
      className={props.className}
      data-testid={props["data-testid"]}
    />
  ),
}));

const themeState = vi.hoisted(() => ({
  resolved: "light" as "light" | "dark",
}));

vi.mock("@/components/theme/ThemeProvider", () => ({
  useThemeOptional: () => ({
    theme: themeState.resolved,
    resolved: themeState.resolved,
    setTheme: () => {},
    toggle: () => {},
  }),
}));

describe("BrandMark", () => {
  afterEach(() => {
    themeState.resolved = "light";
  });

  it("uses dark mono on light theme", () => {
    themeState.resolved = "light";
    render(<BrandMark />);
    const img = screen.getByTestId("brand-mark-image");
    expect(img).toHaveAttribute("src", "/brand/ingenium-mark-mono.png");
    expect(img.className).not.toMatch(/invert/);
  });

  it("uses white inverted mono on dark theme", () => {
    themeState.resolved = "dark";
    render(<BrandMark />);
    const img = screen.getByTestId("brand-mark-image");
    expect(img).toHaveAttribute("src", "/brand/ingenium-mark-mono.png");
    expect(img.className).toMatch(/invert/);
    expect(screen.getByTestId("brand-wordmark").className).toMatch(/text-white/);
  });

  it("can force white on light surfaces", () => {
    themeState.resolved = "light";
    render(<BrandMark variant="white" />);
    expect(screen.getByTestId("brand-mark-image").className).toMatch(/invert/);
  });

  it("can force color variant", () => {
    render(<BrandMark variant="color" />);
    expect(screen.getByTestId("brand-mark-image")).toHaveAttribute(
      "src",
      "/brand/ingenium-mark.png",
    );
  });
});

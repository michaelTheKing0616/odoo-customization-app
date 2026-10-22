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

  it("uses colour mark-light on light theme (png at 32+)", () => {
    themeState.resolved = "light";
    render(<BrandMark size={40} />);
    const img = screen.getByTestId("brand-mark-image");
    expect(img).toHaveAttribute("src", "/brand/ingenium-mark-light.png");
    expect(img.className).not.toMatch(/invert/);
  });

  it("uses colour on-dark mark on dark theme (no invert)", () => {
    themeState.resolved = "dark";
    render(<BrandMark size={40} />);
    const img = screen.getByTestId("brand-mark-image");
    expect(img).toHaveAttribute("src", "/brand/ingenium-mark.png");
    expect(img.className).not.toMatch(/invert/);
    expect(screen.getByTestId("brand-wordmark").className).toMatch(/text-white/);
  });

  it("can force white (on-dark) on light surfaces", () => {
    themeState.resolved = "light";
    render(<BrandMark variant="white" size={40} />);
    const img = screen.getByTestId("brand-mark-image");
    expect(img).toHaveAttribute("src", "/brand/ingenium-mark.png");
    expect(img.className).not.toMatch(/invert/);
  });

  it("can force color variant", () => {
    render(<BrandMark variant="color" size={40} />);
    expect(screen.getByTestId("brand-mark-image")).toHaveAttribute(
      "src",
      "/brand/ingenium-mark.png",
    );
  });

  it("uses small SVG below 32px (default size 28)", () => {
    themeState.resolved = "light";
    render(<BrandMark />);
    expect(screen.getByTestId("brand-mark-image")).toHaveAttribute(
      "src",
      "/brand/ingenium-mark-small-color.svg",
    );
  });

  it("uses small on-dark SVG below 32px in dark theme", () => {
    themeState.resolved = "dark";
    render(<BrandMark size={22} withWordmark={false} />);
    expect(screen.getByTestId("brand-mark-image")).toHaveAttribute(
      "src",
      "/brand/ingenium-mark-small-on-dark.svg",
    );
  });
});

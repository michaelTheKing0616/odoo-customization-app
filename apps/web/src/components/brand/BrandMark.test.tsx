/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BrandMark } from "./BrandMark";

vi.mock("next/image", () => ({
  default: (props: { alt: string; src: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img alt={props.alt} src={props.src} />
  ),
}));

describe("BrandMark", () => {
  it("renders ingenium wordmark and logo", () => {
    render(<BrandMark />);
    expect(screen.getByTestId("brand-wordmark")).toHaveTextContent("ingenium");
    expect(screen.getByAltText("Ingenium")).toHaveAttribute("src", "/brand/ingenium-logo.png");
  });
});

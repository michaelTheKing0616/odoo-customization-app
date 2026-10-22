/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import NotFound from "@/app/not-found";
import ConnectionNotFound from "@/app/connections/[id]/not-found";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(() => {
  cleanup();
});

describe("app route states", () => {
  it("renders root not-found copy and home link", () => {
    render(<NotFound />);
    expect(screen.getByRole("heading", { name: /this page isn.t here/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /go home/i })).toHaveAttribute("href", "/");
  });

  it("renders connection not-found copy and connections link", () => {
    render(<ConnectionNotFound />);
    expect(
      screen.getByRole("heading", { name: /find this connection failed/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view connections/i })).toHaveAttribute(
      "href",
      "/connections",
    );
  });
});

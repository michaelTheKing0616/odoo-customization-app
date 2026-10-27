/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Loading from "@/app/loading";
import RouteError from "@/app/error";
import NotFound from "@/app/not-found";
import ConnectionLoading from "@/app/connections/[id]/loading";
import ConnectionError from "@/app/connections/[id]/error";
import ConnectionNotFound from "@/app/connections/[id]/not-found";
import { Tooltip, TooltipProvider } from "@/components/ui/Tooltip";

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
  vi.useRealTimers();
});

function skeletonCount(container: HTMLElement) {
  return container.querySelectorAll(".shimmer-15").length;
}

describe("app route states", () => {
  it("renders root loading with the kit Skeleton", () => {
    const { container } = render(<Loading />);
    expect(screen.getByText("Loading page")).toBeInTheDocument();
    expect(skeletonCount(container)).toBe(3);
  });

  it("renders root error copy, retry, and home", () => {
    const reset = vi.fn();
    render(<RouteError error={new Error("render failed")} reset={reset} />);
    expect(screen.getByRole("heading", { name: "Load this page failed" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "The app hit an error while rendering. Try again, or return home if the problem continues.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Go home" })).toBeInTheDocument();
  });

  it("renders root not-found copy and home link", () => {
    render(<NotFound />);
    expect(screen.getByRole("heading", { name: /this page isn.t here/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /go home/i })).toHaveAttribute("href", "/");
  });

  it("renders connection loading with the kit Skeleton", () => {
    const { container } = render(<ConnectionLoading />);
    expect(screen.getByText("Loading connection")).toBeInTheDocument();
    expect(skeletonCount(container)).toBe(3);
  });

  it("renders connection error copy, retry, and connections link", () => {
    const reset = vi.fn();
    render(<ConnectionError error={new Error("render failed")} reset={reset} />);
    expect(screen.getByRole("heading", { name: "Load this connection failed" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Something blocked this connection view from rendering. Try again, or pick another connection from the list.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "View connections" })).toHaveAttribute(
      "href",
      "/connections",
    );
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

describe("tooltip keyboard delay", () => {
  it("stays hidden before 125 ms, shows by 200 ms, and Escape removes it", async () => {
    vi.useFakeTimers();
    render(
      <TooltipProvider>
        <Tooltip label="Helper text">
          <button type="button">Trigger button</button>
        </Tooltip>
      </TooltipProvider>,
    );
    const trigger = screen.getByRole("button", { name: "Trigger button" });
    trigger.focus();
    fireEvent.focus(trigger);

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(124);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(76);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Helper text");

    fireEvent.keyDown(document, { key: "Escape", code: "Escape", bubbles: true });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});

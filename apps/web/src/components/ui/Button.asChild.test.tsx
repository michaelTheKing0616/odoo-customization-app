/** @vitest-environment jsdom */
import Link from "next/link";
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "@/components/ui/Button";

afterEach(() => {
  cleanup();
});

describe("Button asChild", () => {
  it("renders an anchor with href instead of a button", () => {
    render(
      <Button asChild variant="secondary">
        <a href="/connect">Go connect</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Go connect" });
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/connect");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("merges button variant classes with the child className", () => {
    render(
      <Button asChild variant="primary" className="btn-extra">
        <a href="/x" className="link-own">
          Link
        </a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Link" });
    expect(link).toHaveClass("link-own");
    expect(link).toHaveClass("btn-extra");
    expect(link).toHaveClass("bg-accent");
  });

  it("calls the anchor onClick when clicked", () => {
    const onAnchorClick = vi.fn();
    render(
      <Button asChild>
        <a href="/y" onClick={onAnchorClick}>
          Click me
        </a>
      </Button>,
    );
    fireEvent.click(screen.getByRole("link", { name: "Click me" }));
    expect(onAnchorClick).toHaveBeenCalledTimes(1);
  });

  it("throws when asChild has a single text child", () => {
    let thrown: unknown;
    try {
      render(<Button asChild>text</Button>);
    } catch (error) {
      thrown = error;
    }
    expect(thrown).toBeInstanceOf(Error);
    expect((thrown as Error).message).toBe(
      "Button: asChild expects a single React element child.",
    );
  });
});

describe("Button asChild with Link, ref, and handlers", () => {
  it("renders a Next Link with merged className", () => {
    render(
      <Button asChild variant="danger" size="sm" className="btn-extra">
        <Link href="/connections" className="link-own">
          Connections
        </Link>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Connections" });
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/connections");
    expect(link).toHaveClass("link-own", "btn-extra", "bg-danger", "h-8");
  });

  it("forwards the Button ref to the rendered child element", () => {
    const ref = React.createRef<HTMLElement>();
    render(
      <Button asChild ref={ref}>
        <a href="/r">Ref target</a>
      </Button>,
    );
    expect(ref.current).toBe(screen.getByRole("link", { name: "Ref target" }));
  });

  it("keeps the child's own ref alongside the Button ref", () => {
    const buttonRef = React.createRef<HTMLElement>();
    const childRef = React.createRef<HTMLAnchorElement>();
    render(
      <Button asChild ref={buttonRef}>
        <a href="/r2" ref={childRef}>
          Both refs
        </a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Both refs" });
    expect(buttonRef.current).toBe(link);
    expect(childRef.current).toBe(link);
  });

  it("calls both the Button and child onClick handlers", () => {
    const onButtonClick = vi.fn();
    const onChildClick = vi.fn();
    render(
      <Button asChild onClick={onButtonClick}>
        <a href="/z" onClick={onChildClick}>
          Both handlers
        </a>
      </Button>,
    );
    fireEvent.click(screen.getByRole("link", { name: "Both handlers" }));
    expect(onButtonClick).toHaveBeenCalledTimes(1);
    expect(onChildClick).toHaveBeenCalledTimes(1);
  });
});

describe("Button asChild disabled", () => {
  it("is not focusable and does not activate when disabled", () => {
    const onButtonClick = vi.fn();
    const onChildClick = vi.fn();
    render(
      <Button asChild disabled onClick={onButtonClick}>
        <a href="/blocked" onClick={onChildClick} tabIndex={0}>
          Blocked
        </a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Blocked" });
    expect(link).toHaveAttribute("aria-disabled", "true");
    expect(link).toHaveAttribute("tabindex", "-1");
    expect(link).toHaveClass("aria-disabled:pointer-events-none");
    expect(link.tabIndex).toBe(-1);
    const notCancelled = fireEvent.click(link);
    expect(notCancelled).toBe(false);
    expect(onButtonClick).not.toHaveBeenCalled();
    expect(onChildClick).not.toHaveBeenCalled();
  });

  it("treats loading as disabled", () => {
    const onChildClick = vi.fn();
    render(
      <Button asChild loading>
        <a href="/wait" onClick={onChildClick}>
          Wait
        </a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Wait" });
    expect(link).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(link);
    expect(onChildClick).not.toHaveBeenCalled();
  });
});

describe("Button default element", () => {
  it("renders a button and calls onClick", () => {
    const onClick = vi.fn();
    render(
      <Button type="button" onClick={onClick}>
        Submit
      </Button>,
    );
    const btn = screen.getByRole("button", { name: "Submit" });
    expect(btn.tagName).toBe("BUTTON");
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

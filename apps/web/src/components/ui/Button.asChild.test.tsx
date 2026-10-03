/** @vitest-environment jsdom */
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

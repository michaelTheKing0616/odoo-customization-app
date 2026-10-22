/** @vitest-environment happy-dom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LiveDemoErrorNotice } from "./LiveDemoErrorNotice";

const diagnose = vi.fn();

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: (text: string) => diagnose(text),
}));

afterEach(() => {
  cleanup();
  diagnose.mockClear();
});

describe("LiveDemoErrorNotice", () => {
  it("shows what/why/next and can diagnose", () => {
    render(
      <LiveDemoErrorNotice message="Attendee timeout" context="launch" onRetry={() => undefined} />,
    );
    expect(screen.getByTestId("live-demo-error-notice")).toBeInTheDocument();
    expect(screen.getByTestId("live-demo-error-message")).toHaveTextContent("Attendee timeout");
    expect(screen.getByTestId("live-demo-error-why")).toHaveTextContent(/Attendee|consent/i);
    expect(screen.getByTestId("live-demo-error-next")).toHaveTextContent(/Diagnose|Refresh/i);
    fireEvent.click(screen.getByRole("button", { name: /Diagnose with Expert/i }));
    expect(diagnose).toHaveBeenCalled();
  });
});

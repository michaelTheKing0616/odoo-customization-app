import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ErrorNotice, newTraceId, supportText } from "./ErrorNotice";

describe("68 errors that offer the fix", () => {
  it("shows why, next, a fix button and a trace", () => {
    const onFix = vi.fn();
    render(<ErrorNotice message="Odoo refused the login." why="The password changed." next="Update it in Connect." fix={{ label: "Update password", onClick: onFix }} showDiagnose={false} />);
    fireEvent.click(screen.getByTestId("error-notice-fix"));
    expect(onFix).toHaveBeenCalled();
    expect(screen.getByTestId("error-notice-why").textContent).toContain("password");
    expect(screen.getByTestId("error-notice-trace").textContent).toMatch(/^ING-/);
  });
  it("support text carries trace, WAT time and message", () => {
    const t = supportText({ trace: "ING-AB", title: "Request failed", message: "x", at: new Date("2026-10-20T13:00:00Z") });
    expect(t).toContain("ING-AB");
    expect(t).toContain("14:00 WAT");
    expect(newTraceId(1, 0)).toMatch(/^ING-[0-9A-Z]+$/);
  });
});

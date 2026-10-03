/** @vitest-environment jsdom */
import React, { useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TotpCodeInput } from "@/components/auth/TotpCodeInput";

beforeAll(() => {
  if (typeof document.elementFromPoint !== "function") {
    document.elementFromPoint = () => null;
  }
  const originalSupports = CSS.supports.bind(CSS);
  vi.spyOn(CSS, "supports").mockImplementation((property, value) => {
    if (property === "-webkit-touch-callout" && value === "none") {
      return true;
    }
    return typeof value === "undefined"
      ? originalSupports(property)
      : originalSupports(property, value);
  });
});

function Harness() {
  const [value, setValue] = useState("");
  return (
    <>
      <TotpCodeInput value={value} onChange={setValue} />
      <output data-testid="totp-value">{value}</output>
    </>
  );
}

afterEach(() => {
  cleanup();
});

describe("TotpCodeInput", () => {
  it("accepts a pasted 6-digit code and uses one-time-code autocomplete", async () => {
    render(<Harness />);
    const input = document.querySelector("[data-input-otp]") as HTMLInputElement;
    expect(input).toBeTruthy();
    expect(input).toHaveAttribute("autocomplete", "one-time-code");

    fireEvent.focus(input);
    const pasteEvent = new Event("paste", { bubbles: true, cancelable: true });
    Object.defineProperty(pasteEvent, "clipboardData", {
      value: {
        getData: (format: string) => (format === "text/plain" ? "123456" : ""),
      },
    });
    input.dispatchEvent(pasteEvent);

    await waitFor(() => {
      expect(screen.getByTestId("totp-value")).toHaveTextContent("123456");
    });
    expect(input.value).toBe("123456");
  });
});

/** @vitest-environment jsdom */
import React, { useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TotpCodeInput, type TotpCodeInputProps } from "@/components/auth/TotpCodeInput";

beforeAll(() => {
  if (typeof document.elementFromPoint !== "function") {
    document.elementFromPoint = () => null;
  }
  const originalSupports = CSS.supports.bind(CSS);
  vi.spyOn(CSS, "supports").mockImplementation(((property: string, value?: string) => {
    if (property === "-webkit-touch-callout" && value === "none") {
      return true;
    }
    return typeof value === "undefined"
      ? originalSupports(property)
      : originalSupports(property, value);
  }) as typeof CSS.supports);
});

type HarnessProps = Partial<Omit<TotpCodeInputProps, "value" | "onChange">>;

function Harness(props: HarnessProps) {
  const [value, setValue] = useState("");
  return (
    <>
      <TotpCodeInput label="Two-factor code" value={value} onChange={setValue} {...props} />
      <output data-testid="totp-value">{value}</output>
    </>
  );
}

function paste(input: HTMLInputElement, text: string) {
  fireEvent.focus(input);
  const pasteEvent = new Event("paste", { bubbles: true, cancelable: true });
  Object.defineProperty(pasteEvent, "clipboardData", {
    value: { getData: (format: string) => (format === "text/plain" ? text : "") },
  });
  input.dispatchEvent(pasteEvent);
}

afterEach(() => {
  cleanup();
});

describe("TotpCodeInput", () => {
  it("ties the visible label to the input for screen readers", () => {
    render(<Harness description="The 6 digits shown in your authenticator app." />);
    const input = screen.getByLabelText("Two-factor code");
    expect(input).toHaveAttribute("data-input-otp");
    expect(input).toHaveAccessibleDescription("The 6 digits shown in your authenticator app.");
  });

  it("asks for a numeric one-time code with 6 slots", () => {
    render(<Harness />);
    const input = screen.getByLabelText("Two-factor code");
    expect(input).toHaveAttribute("autocomplete", "one-time-code");
    expect(input).toHaveAttribute("inputmode", "numeric");
    expect(input).toHaveAttribute("maxlength", "6");
    expect(document.querySelectorAll("[data-slot='totp-slot']")).toHaveLength(6);
  });

  it("accepts typed digits one slot at a time", async () => {
    render(<Harness />);
    const input = screen.getByLabelText("Two-factor code") as HTMLInputElement;
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "1" } });
    fireEvent.change(input, { target: { value: "12" } });
    await waitFor(() => expect(screen.getByTestId("totp-value")).toHaveTextContent("12"));
    const slots = document.querySelectorAll("[data-slot='totp-slot']");
    expect(slots[0]).toHaveTextContent("1");
    expect(slots[1]).toHaveTextContent("2");
  });

  it("rejects non-digit characters", async () => {
    render(<Harness />);
    const input = screen.getByLabelText("Two-factor code") as HTMLInputElement;
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "1" } });
    fireEvent.change(input, { target: { value: "1a" } });
    await waitFor(() => expect(screen.getByTestId("totp-value")).toHaveTextContent("1"));
    expect(screen.getByTestId("totp-value").textContent).toBe("1");
    expect(input.value).toBe("1");
  });

  it("fills all 6 slots from a pasted code and reports completion", async () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    const input = screen.getByLabelText("Two-factor code") as HTMLInputElement;
    paste(input, "123456");
    await waitFor(() => expect(screen.getByTestId("totp-value")).toHaveTextContent("123456"));
    expect(input.value).toBe("123456");
    const slots = Array.from(document.querySelectorAll("[data-slot='totp-slot']"));
    expect(slots.map((slot) => slot.textContent)).toEqual(["1", "2", "3", "4", "5", "6"]);
    await waitFor(() => expect(onComplete).toHaveBeenCalledWith("123456"));
  });

  it("strips spaces and dashes from a pasted code", async () => {
    render(<Harness />);
    const input = screen.getByLabelText("Two-factor code") as HTMLInputElement;
    paste(input, "123 456");
    await waitFor(() => expect(screen.getByTestId("totp-value")).toHaveTextContent("123456"));
  });

  it("shows a one-sentence error, marks the input invalid, and describes it", () => {
    render(<Harness error="Enter all 6 digits of the code from your authenticator app." />);
    const input = screen.getByLabelText("Two-factor code");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter all 6 digits of the code from your authenticator app.",
    );
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(
      "Enter all 6 digits of the code from your authenticator app.",
    );
  });

  it("disables the field and sets aria-busy while verifying", () => {
    const { container } = render(<Harness busy />);
    expect(screen.getByLabelText("Two-factor code")).toBeDisabled();
    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
  });

  it("only blinks the caret when motion is allowed", async () => {
    render(<Harness />);
    const input = screen.getByLabelText("Two-factor code") as HTMLInputElement;
    fireEvent.focus(input);
    await waitFor(() => expect(document.querySelector(".animate-pulse, [class*='animate-pulse']")).not.toBeNull());
    const caret = document.querySelector("[class*='animate-pulse']") as HTMLElement;
    expect(caret.className).toContain("motion-safe:animate-pulse");
    expect(caret.className).not.toMatch(/(^|\s)animate-pulse/);
  });
});

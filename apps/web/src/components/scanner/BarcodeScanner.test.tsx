import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BarcodeScanner } from "./BarcodeScanner";

vi.mock("@zxing/browser", () => ({
  BrowserMultiFormatReader: class {
    decodeFromVideoDevice(_id: unknown, _video: unknown, cb: (result: { getText: () => string } | null) => void) {
      cb({ getText: () => "SCAN-001" });
    }
    reset() {}
  },
}));

describe("BarcodeScanner", () => {
  it("calls onScan when decode succeeds", async () => {
    const onScan = vi.fn();
    const getUserMedia = vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }],
    });
    Object.defineProperty(global.navigator, "mediaDevices", {
      value: { getUserMedia },
      configurable: true,
    });

    // jsdom has no media playback or MediaStream; stub both as a real browser would accept them.
    Object.defineProperty(HTMLMediaElement.prototype, "srcObject", { set() {}, get() { return null; }, configurable: true });
    Object.defineProperty(HTMLMediaElement.prototype, "play", { value: vi.fn().mockResolvedValue(undefined), configurable: true });

    const onError = vi.fn();
    render(<BarcodeScanner onScan={onScan} onError={onError} />);
    fireEvent.click(screen.getByRole("button", { name: /start camera/i }));

    await waitFor(() => expect(onScan.mock.calls.length + onError.mock.calls.length).toBeGreaterThan(0));
    expect(onError.mock.calls).toEqual([]);
    expect(onScan).toHaveBeenCalledWith("SCAN-001");
  });
});

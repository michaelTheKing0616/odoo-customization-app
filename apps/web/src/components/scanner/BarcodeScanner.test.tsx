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

    render(<BarcodeScanner onScan={onScan} />);
    fireEvent.click(screen.getByRole("button", { name: /start camera/i }));

    await waitFor(() => expect(onScan).toHaveBeenCalledWith("SCAN-001"));
  });
});

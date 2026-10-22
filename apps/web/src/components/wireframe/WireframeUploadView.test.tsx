/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: import("react").ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api", () => ({
  api: {
    wireframeStatus: vi.fn(),
    wireframeRead: vi.fn(),
    wireframeClarify: vi.fn(),
    wireframeMap: vi.fn(() => new Promise(() => undefined)),
  },
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

vi.mock("@/components/studio/StudioPreviewPane", () => ({
  StudioPreviewPane: () => <div data-testid="draft-odoo-preview">Stage H preview</div>,
}));

vi.mock("@/components/studio/ClarifyInterstitial", () => ({
  ClarifyInterstitial: ({
    clarification,
  }: {
    clarification: { question: string };
  }) => <div data-testid="studio-clarify">{clarification.question}</div>,
}));

import { api } from "@/lib/api";
import { WireframeUploadView } from "./WireframeUploadView";

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }),
  });
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("WireframeUploadView", () => {
  it("is an operate screen with a visible file input and Gemini-not-connected copy", async () => {
    vi.mocked(api.wireframeStatus).mockResolvedValue({
      provider: "gemini",
      connected: false,
      message: "Gemini is not connected. Add GEMINI_API_KEY to read a photographed sketch.",
      default_provider: "gemini",
    });

    render(<WireframeUploadView connectionId="conn-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("wireframe-gemini-missing").textContent).toMatch(/gemini is not connected/i);
    });
    expect(screen.getByLabelText("Photograph")).toBeTruthy();
    expect(screen.getByTestId("wireframe-file").getAttribute("type")).toBe("file");
    expect(screen.queryByRole("button", { name: /apply/i })).toBeNull();
    expect(screen.getByTestId("wireframe-upload").textContent).not.toMatch(/purple|hero|feature/i);
    const note = screen.getByTestId("wireframe-frontier-note");
    expect(note.textContent).toMatch(/claude can be selected later/i);
    expect(note.textContent).toMatch(/not the provider in use today/i);
    expect(screen.getByTestId("wireframe-read")).toBeDisabled();
  });

  it("shows the image and a Stage H preview after a successful read", async () => {
    vi.mocked(api.wireframeStatus).mockResolvedValue({
      provider: "gemini",
      connected: true,
      message: "Gemini is connected.",
      default_provider: "gemini",
    });
    vi.mocked(api.wireframeRead).mockResolvedValue({
      status: "review",
      connected: true,
      provider: "gemini",
      clarification: null,
      spec: { _wireframe: { source: "sketch", stage_h: true } },
      form_preview: { type: "form", model: "x_visitor_log", title: "Visitor Log", groups: [] },
      apply_ready: false,
      sketch: { title: "Visitor Log", regions: [] },
    });

    render(<WireframeUploadView connectionId="conn-1" />);
    await waitFor(() => expect(api.wireframeStatus).toHaveBeenCalled());

    const input = screen.getByTestId("wireframe-file") as HTMLInputElement;
    const file = new File(["abc"], "sketch.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByTestId("wireframe-image")).toBeTruthy();
    fireEvent.click(screen.getByTestId("wireframe-read"));
    await waitFor(() => {
      expect(screen.getByTestId("wireframe-stage-h")).toBeTruthy();
    });
    expect(screen.queryByRole("button", { name: /apply/i })).toBeNull();
    expect(api.wireframeRead).toHaveBeenCalledWith("conn-1", file);
  });

  it("shows the clarify question when the reader is unsure", async () => {
    vi.mocked(api.wireframeStatus).mockResolvedValue({
      provider: "gemini",
      connected: true,
      message: "Gemini is connected.",
      default_provider: "gemini",
    });
    vi.mocked(api.wireframeRead).mockResolvedValue({
      status: "clarify",
      connected: true,
      provider: "gemini",
      clarification: {
        merge_key: "wireframe_region",
        question: "What is the unlabeled region on this sketch?",
      },
      spec: null,
      apply_ready: false,
      sketch: { title: "Visitor Log", regions: [{ id: "r2", label: "" }] },
    });

    render(<WireframeUploadView connectionId="conn-1" />);
    await waitFor(() => expect(api.wireframeStatus).toHaveBeenCalled());
    const input = screen.getByTestId("wireframe-file") as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(["abc"], "sketch.png", { type: "image/png" })] },
    });
    fireEvent.click(screen.getByTestId("wireframe-read"));
    await waitFor(() => {
      expect(screen.getByTestId("wireframe-clarify").textContent).toMatch(/unlabeled/i);
    });
  });
});

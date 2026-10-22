/** @vitest-environment happy-dom */
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { passthrough } = vi.hoisted(() => ({
  passthrough: ({ children }: { children: ReactNode }) => children,
}));

vi.mock("@/providers/QueryProvider", () => ({ QueryProvider: passthrough }));
vi.mock("@/components/theme/ThemeProvider", () => ({ ThemeProvider: passthrough }));
vi.mock("@/components/ui/Tooltip", () => ({ TooltipProvider: passthrough }));
vi.mock("./layout-inner", () => ({
  default: function SuspendingShell(): ReactNode {
    throw new Promise(() => undefined);
  },
}));

import ConnectionLayout from "./layout";

afterEach(() => {
  cleanup();
});

describe("connection layout shell fallback", () => {
  it("renders the connection skeleton instead of loading text while the shell suspends", () => {
    const { container } = render(
      <ConnectionLayout>
        <p>child</p>
      </ConnectionLayout>,
    );

    expect(screen.getByText("Loading connection")).toBeInTheDocument();
    expect(container.querySelectorAll(".motion-safe\\:animate-pulse").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Loading shell/)).toBeNull();
  });
});

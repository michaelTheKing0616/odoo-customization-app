/**
 * F1-HYDRATE. Server HTML vs hydrateRoot for the surfaces this file can mount.
 * Failure strings are the P0-7 crawl tokens: Hydration, did not match,
 * Text content does not match. The 126-route Playwright crawl is not this file.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, createElement, type ReactElement } from "react";
import { hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { writeShell } from "./shellCache";

const HYDRATION = /Hydration|did not match|Text content does not match/;
const SHELL_NAME = "Cache Sentinel Shop";
const CONNECT_NAME = "Connect Sentinel Shop";

const apiMocks = vi.hoisted(() => ({
  listConnections: vi.fn(),
  getConnection: vi.fn(),
  billingEntitlements: vi.fn(),
  getProductionReadiness: vi.fn(),
  expertSuggestedPrompts: vi.fn(),
  expertNLSearch: vi.fn(),
  listModels: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/connections/conn-1",
  useRouter: () => ({ push: vi.fn(), prefetch: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: import("react").ReactNode;
  }) => createElement("a", { href: typeof href === "string" ? href : "", ...rest }, children),
}));

vi.mock("@/lib/api", () => ({ api: apiMocks }));

vi.mock("@/components/expert/ExpertPanel", () => ({ ExpertPanel: () => null }));
vi.mock("@/components/expert/ExpertBubble", () => ({ ExpertBubble: () => null }));
vi.mock("@/lib/expert-diagnostics", () => ({
  ExpertDiagnoseListener: () => null,
  diagnoseWithExpert: vi.fn(),
}));

vi.mock("@/context/ShellContext", () => ({
  useShell: () => ({
    commandOpen: false,
    setCommandOpen: vi.fn(),
    setExpertOpen: vi.fn(),
    openExpert: vi.fn(),
    setUiContext: vi.fn(),
    uiContext: {},
    sidebarCollapsed: false,
    setSidebarCollapsed: vi.fn(),
  }),
}));

vi.mock("@/components/connect/connect-operate.css", () => ({}));

import ConnectPage from "@/app/connect/page";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import { AppShell } from "@/components/shell/AppShell";
import { ConnectionSwitcher } from "@/components/shell/ConnectionSwitcher";
import { ThemeProvider, useTheme } from "@/components/theme/ThemeProvider";
import { ThemeScript } from "@/components/theme/ThemeScript";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { GoToKeys, Keycap, Money, RelativeTime } from "@/components/ui/craft";

const roots: Root[] = [];

function source(rel: string): string {
  return readFileSync(join(__dirname, rel), "utf8");
}

function shellConnection(name: string) {
  return {
    id: "conn-1",
    name,
    url: "https://odoo.example",
    db_name: "shop",
    username: "ada",
    server_version: "19.0",
    write_mode: "observer" as const,
    is_test_copy: false,
    created_at: null,
    updated_at: null,
    capabilities: null,
  };
}

function asText(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

function hits(errors: string[]): string[] {
  return errors.filter((line) => HYDRATION.test(line));
}

async function hydrateInto(
  html: string,
  node: ReactElement,
): Promise<{ errors: string[]; text: string; markup: string }> {
  const host = document.createElement("div");
  host.innerHTML = html;
  document.body.appendChild(host);
  const errors: string[] = [];
  const prev = console.error;
  console.error = (...args: unknown[]) => {
    errors.push(args.map(asText).join(" "));
  };
  try {
    await act(async () => {
      roots.push(
        hydrateRoot(host, node, {
          onRecoverableError(error) {
            errors.push(asText(error));
          },
        }),
      );
    });
  } finally {
    console.error = prev;
  }
  return { errors, text: host.textContent ?? "", markup: host.innerHTML };
}

function ThemeProbe() {
  const { theme, resolved } = useTheme();
  return createElement("output", { "data-testid": "theme-probe" }, `${theme}:${resolved}`);
}

function shellTree(client: QueryClient) {
  return createElement(
    QueryClientProvider,
    { client },
    createElement(ThemeProvider, null, createElement(AppShell, {
      connectionId: "conn-1",
      children: createElement("p", null, "page body"),
    })),
  );
}

beforeEach(() => {
  localStorage.clear();
  document.body.innerHTML = "";
  document.documentElement.classList.remove("dark");
  document.documentElement.removeAttribute("data-density");
  document.documentElement.removeAttribute("data-reading-comfort");
  document.documentElement.removeAttribute("data-odoo-dim");
  apiMocks.listConnections.mockReset();
  apiMocks.getConnection.mockReset();
  apiMocks.billingEntitlements.mockReset();
  apiMocks.getProductionReadiness.mockReset();
  apiMocks.listConnections.mockResolvedValue([]);
  apiMocks.getConnection.mockImplementation(() => new Promise(() => undefined));
  apiMocks.billingEntitlements.mockRejectedValue(Object.assign(new Error("signed out"), { status: 401 }));
  apiMocks.getProductionReadiness.mockResolvedValue({
    passed: true,
    items: [],
    first_write_acknowledged: true,
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new Error("no network in f1 hydrate");
    }),
  );
});

afterEach(() => {
  while (roots.length) roots.pop()?.unmount();
  document.body.innerHTML = "";
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("F1-HYDRATE", () => {
  it("Connect load paints the saved-list skeleton and hydrates without a mismatch", async () => {
    apiMocks.listConnections.mockResolvedValue([shellConnection(CONNECT_NAME)]);
    const node = createElement(ConnectPage);
    const html = renderToString(node);
    expect(html).toContain('data-testid="connect-saved-loading"');
    expect(html).not.toContain(CONNECT_NAME);
    const hydrated = await hydrateInto(html, createElement(ConnectPage));
    expect(hits(hydrated.errors)).toEqual([]);
    expect(hydrated.text).toContain(CONNECT_NAME);
    expect(hydrated.markup).not.toContain('data-testid="connect-saved-loading"');
  });

  it("shell cache stays out of the server tree until after mount", async () => {
    const shell = source("../components/shell/AppShell.tsx");
    expect(shell).toContain("const hydrated = useHydrated()");
    expect(shell.match(/hydrated\s*\?\s*readShell\(/g)).toHaveLength(3);
    expect(shell).toContain("hydrated ? readRecent(connectionId) : []");
    const cached = shellConnection(SHELL_NAME);
    writeShell("connection:conn-1", cached);
    writeShell("connections", [cached]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const html = renderToString(shellTree(client));
    expect(html).toContain('data-testid="app-shell-loading"');
    expect(html).not.toContain(SHELL_NAME);
    const hydrated = await hydrateInto(html, shellTree(client));
    expect(hits(hydrated.errors)).toEqual([]);
    expect(hydrated.text).toContain(SHELL_NAME);
  });

  it("Lagos sunset toggles the document class from the no-flash script, not a different React tree", async () => {
    const layout = source("../app/layout.tsx");
    expect(layout).toContain("<ThemeScript />");
    expect(layout).toMatch(/<html[^>]*suppressHydrationWarning/);
    const script = source("../components/theme/ThemeScript.tsx");
    expect(script).toContain("s==='sunset'");
    expect(script).toContain("classList.toggle");
    localStorage.setItem("odoo-custom-theme", "sunset");
    const tree = () => createElement(ThemeProvider, null, createElement(ThemeScript), createElement(ThemeProbe));
    const html = renderToString(tree());
    expect(html).toContain("system:light");
    expect(html).toContain("s==='sunset'");
    expect(html).not.toContain("sunset:");
    const again = renderToString(tree());
    expect(again).toBe(html);
    const hydrated = await hydrateInto(html, tree());
    expect(hits(hydrated.errors)).toEqual([]);
  });

  it("platform keycap starts from a fixed glyph and hydrates cleanly", async () => {
    expect(source("../components/ui/craft.tsx")).toMatch(/const \[mac, setMac\] = React\.useState\(true\)/);
    const node = () => createElement(Keycap, { keys: "Mod+K" });
    const html = renderToString(node());
    expect(html).toContain("⌘");
    expect(html).not.toContain("Ctrl");
    const hydrated = await hydrateInto(html, node());
    expect(hits(hydrated.errors)).toEqual([]);
  });

  it("connection switcher ids come from useId and the closed menu matches the server", async () => {
    expect(source("../components/shell/ConnectionSwitcher.tsx")).toMatch(/const id = useId\(\)/);
    const current = shellConnection(SHELL_NAME);
    const node = () => createElement(ConnectionSwitcher, { current, connections: [current] });
    const html = renderToString(node());
    expect(renderToString(node())).toBe(html);
    expect(html).toContain(SHELL_NAME);
    const hydrated = await hydrateInto(html, node());
    expect(hits(hydrated.errors)).toEqual([]);
    expect(hydrated.text).toContain(SHELL_NAME);
  });

  it("first-write storage is read in an effect, so the dialog is absent from server HTML", async () => {
    const node = () => createElement(FirstWriteInterstitial, { connection: shellConnection(SHELL_NAME) });
    const html = renderToString(node());
    expect(html).not.toContain("Before your first write");
    const hydrated = await hydrateInto(html, node());
    expect(hits(hydrated.errors)).toEqual([]);
  });

  it("density, reading comfort, and odoo dim apply from GoToKeys only after mount", async () => {
    localStorage.setItem("ingenium.density", "compact");
    localStorage.setItem("ingenium.readingComfort", "on");
    localStorage.setItem("ingenium.odooDim", "on");
    const html = renderToString(createElement(GoToKeys));
    expect(html).toBe("");
    expect(document.documentElement.hasAttribute("data-density")).toBe(false);
    expect(document.documentElement.hasAttribute("data-reading-comfort")).toBe(false);
    expect(document.documentElement.hasAttribute("data-odoo-dim")).toBe(false);
    const hydrated = await hydrateInto(html, createElement(GoToKeys));
    expect(hits(hydrated.errors)).toEqual([]);
    expect(document.documentElement.getAttribute("data-density")).toBe("compact");
    expect(document.documentElement.hasAttribute("data-reading-comfort")).toBe(true);
    expect(document.documentElement.hasAttribute("data-odoo-dim")).toBe(true);
  });

  // Defect, not fixed here: ErrorNotice.tsx useState(() => newTraceId()) paints a new ING-* id.
  it.fails("error notice trace is stable across server and client", async () => {
    const props = { message: "Could not save the connection", showDiagnose: false };
    const html = renderToString(createElement(ErrorNotice, props));
    const serverTrace = /data-testid="error-notice-trace">([^<]+)/.exec(html)?.[1] ?? "";
    const hydrated = await hydrateInto(html, createElement(ErrorNotice, props));
    expect(hits(hydrated.errors)).toEqual([]);
    const clientTrace = hydrated.text.match(/ING-[0-9A-Z]+/)?.[0] ?? "";
    expect(clientTrace).toBe(serverTrace);
    expect(serverTrace).toMatch(/^ING-/);
  });

  // Defect, not fixed here: RelativeTime paints Date.now() into the server tree.
  it.fails("relative time is not painted into the server tree", () => {
    const html = renderToString(createElement(RelativeTime, { value: "2020-01-01T00:00:00.000Z" }));
    expect(html).not.toMatch(/ago|just now/);
  });

  it("money uses the fixed en-NG format and hydrates to the same text", async () => {
    expect(source("../components/ui/craft.tsx")).toMatch(/new Intl\.NumberFormat\("en-NG"/);
    const node = () => createElement(Money, { amount: 1250.5, currency: "NGN" });
    const html = renderToString(node());
    expect(html).toContain("₦");
    const hydrated = await hydrateInto(html, node());
    expect(hits(hydrated.errors)).toEqual([]);
    expect(hydrated.text.replace(/[\s\u00a0\u202f,]/g, "")).toContain("₦1250.50");
  });
});

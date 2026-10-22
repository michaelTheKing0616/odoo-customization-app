import { act } from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { readShell, useHydrated, writeShell } from "./shellCache";

function Frame() {
  const hydrated = useHydrated();
  const c = hydrated ? readShell<{ name: string }>("connection:x") : undefined;
  return <div data-testid="frame">{c ? `shell:${c.name}` : "app-shell-loading"}</div>;
}

describe("shell cache hydration (142)", () => {
  it("server and first client render match even with a warm cache; cache shows after mount", async () => {
    writeShell("connection:x", { name: "Shop" });
    const html = renderToString(<Frame />);
    expect(html).toContain("app-shell-loading");
    const host = document.createElement("div");
    host.innerHTML = html;
    document.body.appendChild(host);
    const errors: unknown[] = [];
    await act(async () => {
      hydrateRoot(host, <Frame />, { onRecoverableError: (e) => errors.push(e) });
    });
    expect(errors).toEqual([]);
    expect(host.textContent).toBe("shell:Shop");
  });
});

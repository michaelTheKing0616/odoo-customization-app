import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

const toastSuccess = vi.fn();
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { success: (...a: unknown[]) => toastSuccess(...a) }) }));

import { StockAppInstallCard } from "@/components/studio/StockAppInstallCard";
import type { StudioClarification } from "@/lib/studio-session";

const QUESTION =
  "Your request edits quotations, which come from the Sales app. Install Sales to continue?";

function salesClarification(installable = true): StudioClarification {
  return {
    kind: "stock_app_install",
    merge_key: "stock_app_install",
    question: QUESTION,
    help: "Sales is not installed, so there is no quotation to put this on yet.",
    options: [
      { id: "install", label: "Install Sales and continue" },
      { id: "decline", label: "Not now" },
    ],
    stock_app: {
      module: "sale",
      app_label: "Sales",
      model: "sale.order",
      noun: "quotations",
      installable,
      question: QUESTION,
      reason: "Sales is not installed, so there is no quotation to put this on yet.",
      install_label: installable ? "Install Sales and continue" : "",
      decline_label: installable ? "Not now" : "Close",
    },
  };
}

function deferred() {
  let resolve!: () => void;
  let reject!: (err: Error) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

afterEach(() => {
  cleanup();
  toastSuccess.mockReset();
});

describe("StockAppInstallCard", () => {
  it("states why and offers install or not now, without asking for an app name", () => {
    render(
      <StockAppInstallCard
        clarification={salesClarification()}
        onInstall={vi.fn()}
        onDecline={vi.fn()}
      />,
    );
    const card = screen.getByTestId("studio-stock-app");
    expect(card.textContent).toContain(QUESTION);
    expect(card.textContent).toContain("Sales is not installed");
    expect(screen.getByTestId("studio-stock-app-install").textContent).toBe(
      "Install Sales and continue",
    );
    expect(screen.getByTestId("studio-stock-app-decline").textContent).toBe("Not now");
    expect(card.querySelector("input, select, textarea")).toBeNull();
  });

  it("shows a loading state while installing, then toasts success", async () => {
    const pending = deferred();
    render(
      <StockAppInstallCard
        clarification={salesClarification()}
        onInstall={() => pending.promise}
        onDecline={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("studio-stock-app-install"));
    const install = screen.getByTestId("studio-stock-app-install") as HTMLButtonElement;
    expect(install.disabled).toBe(true);
    expect(install.textContent).toContain("Installing Sales");
    expect((screen.getByTestId("studio-stock-app-decline") as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId("studio-stock-app-status").textContent).toMatch(/Installing Sales/);
    expect(screen.getByTestId("studio-stock-app").getAttribute("aria-busy")).toBe("true");
    await act(async () => {
      pending.resolve();
      await pending.promise;
    });
    expect(toastSuccess).toHaveBeenCalledWith("Sales is installed", expect.anything());
  });

  it("shows a one-sentence error and lets the user retry", async () => {
    const onInstall = vi
      .fn()
      .mockRejectedValueOnce(
        new Error("Sales could not be installed. Odoo did not finish the install.\nTraceback (most recent call last)"),
      );
    render(
      <StockAppInstallCard
        clarification={salesClarification()}
        onInstall={onInstall}
        onDecline={vi.fn()}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByTestId("studio-stock-app-install"));
    });
    const error = await screen.findByTestId("studio-stock-app-error");
    expect(error.textContent).toContain("Sales was not installed");
    expect(error.textContent).toContain("Odoo did not finish the install.");
    expect(error.textContent).not.toContain("Traceback");
    expect(screen.getByRole("alert")).toBeTruthy();
    const retry = screen.getByTestId("studio-stock-app-install") as HTMLButtonElement;
    expect(retry.disabled).toBe(false);
    expect(retry.textContent).toBe("Try installing Sales again");
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("declines through Not now", async () => {
    const onDecline = vi.fn().mockResolvedValue(undefined);
    const onInstall = vi.fn();
    render(
      <StockAppInstallCard
        clarification={salesClarification()}
        onInstall={onInstall}
        onDecline={onDecline}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByTestId("studio-stock-app-decline"));
    });
    expect(onDecline).toHaveBeenCalledTimes(1);
    expect(onInstall).not.toHaveBeenCalled();
  });

  it("offers no install button for an app that cannot be installed here", () => {
    render(
      <StockAppInstallCard
        clarification={salesClarification(false)}
        onInstall={vi.fn()}
        onDecline={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("studio-stock-app-install")).toBeNull();
    expect(screen.getByTestId("studio-stock-app-decline").textContent).toBe("Close");
  });
});

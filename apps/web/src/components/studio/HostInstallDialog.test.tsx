/** @vitest-environment jsdom */
import { describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { HostInstallPanel } from "@/components/studio/HostInstallDialog";

const SALE_OFFER = {
  module: "sale",
  label: "Sales",
  models: ["sale.order", "sale.order.line"],
  message:
    "This Option A module inherits sale.order, sale.order.line. Those models come from the stock Sales app (sale).",
};

describe("HostInstallPanel", () => {
  it("opens a confirm dialog for the missing Sales app", () => {
    const onInstall = vi.fn();
    render(
      <HostInstallPanel
        offers={[SALE_OFFER]}
        autoOpen={false}
        onInstall={onInstall}
      />,
    );
    expect(screen.getByTestId("studio-host-install-sale").textContent).toMatch(/Sales is not on this connection/);
    fireEvent.click(screen.getByTestId("studio-host-install-open-sale"));
    const dialog = screen.getByTestId("studio-host-install-dialog");
    expect(dialog.textContent).toMatch(/Install Sales on this connection/);
    expect(dialog.textContent).toMatch(/sale\.order/);
    expect(dialog.textContent).toMatch(/sale\.order\.line/);
    expect(dialog.textContent).toMatch(/do not click Install this app/i);
    const confirm = screen.getByTestId("studio-host-install-confirm");
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByTestId("studio-host-install-phrase"), {
      target: { value: "I understand the risks" },
    });
    expect(confirm).not.toBeDisabled();
    fireEvent.click(confirm);
    expect(onInstall).toHaveBeenCalledWith(SALE_OFFER, "I understand the risks");
    cleanup();
  });
});

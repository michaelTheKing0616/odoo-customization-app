/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BridgeContractStudio, type ValidateFn } from "./BridgeContractStudio";
import { classifyResult, type ContractForm } from "@/lib/bridgeContractScreen";

afterEach(() => cleanup());

const FILLED: ContractForm = {
  odooId: "odoo-main",
  thirdId: "shopify-store",
  direction: "inbound",
  conflict: "",
  money: true,
  moneyPolicy: "odoo_wins",
};

function fill(odoo: string, third: string) {
  fireEvent.change(screen.getByTestId("bridge-odoo-id"), { target: { value: odoo } });
  fireEvent.change(screen.getByTestId("bridge-third-id"), { target: { value: third } });
}

describe("BridgeContractStudio", () => {
  it("renders the studio: one teal primary, quiet honesty, sheet ledger, no risk note", () => {
    render(<BridgeContractStudio validateContract={vi.fn()} />);
    expect(screen.getByRole("heading", { level: 1, name: "Contract Studio" })).toBeInTheDocument();
    const primaries = document.querySelectorAll("button.bg-accent");
    expect(primaries).toHaveLength(1);
    expect(primaries[0]).toHaveTextContent("Validate tier I");
    expect(screen.getByTestId("bridge-honesty")).toHaveTextContent("Read-only check. Nothing connects, sends, or syncs.");
    expect(screen.getByTestId("bridge-status-chip")).toHaveTextContent("Draft");
    expect(screen.getByTestId("bridge-result-idle")).toBeInTheDocument();
    expect(screen.getByTestId("bridge-check-distinct")).toHaveAttribute("data-status", "wait");
    expect(screen.getByTestId("bridge-check-odoo_verified")).toHaveAttribute("data-status", "wait");
    expect(screen.getByTestId("bridge-check-conflict")).toHaveAttribute("data-status", "na");
    expect(screen.queryByTestId("bridge-risk")).toBeNull();
    expect(screen.getByTestId("bridge-reset-btn")).toBeDisabled();
    expect(document.body.textContent ?? "").not.toMatch(/[\u2014\u2013]/);
  });

  it("canvas endpoint focuses its inspector field", async () => {
    render(<BridgeContractStudio validateContract={vi.fn()} />);
    fireEvent.click(screen.getByTestId("bridge-node-third"));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("bridge-third-id")));
  });

  it("amber risk note appears only when Remote wins can overwrite Odoo", () => {
    render(<BridgeContractStudio initialForm={FILLED} validateContract={vi.fn()} />);
    expect(screen.queryByTestId("bridge-risk")).toBeNull();
    fireEvent.click(screen.getByTestId("bridge-money-policy-remote_wins"));
    expect(screen.getByTestId("bridge-risk")).toHaveTextContent("overwrite Odoo order totals");
    fireEvent.click(screen.getByTestId("bridge-money"));
    expect(screen.queryByTestId("bridge-risk")).toBeNull();
  });

  it("blocks submit with per-field errors and focuses the first one", async () => {
    const validate = vi.fn<ValidateFn>();
    render(<BridgeContractStudio validateContract={validate} />);
    fireEvent.click(screen.getByTestId("bridge-validate-btn"));
    expect(validate).not.toHaveBeenCalled();
    expect(screen.getByTestId("bridge-error-odooId")).toHaveTextContent("Enter the Odoo connection id.");
    expect(screen.getByTestId("bridge-error-thirdId")).toBeInTheDocument();
    expect(screen.getByTestId("bridge-odoo-id")).toHaveAttribute("aria-invalid", "true");
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("bridge-odoo-id")));
    // Inline re-validation once the user fixes the field.
    fireEvent.change(screen.getByTestId("bridge-odoo-id"), { target: { value: "odoo-main" } });
    expect(screen.queryByTestId("bridge-error-odooId")).toBeNull();
  });

  it("two-way reveals the conflict rule and requires it", async () => {
    render(<BridgeContractStudio validateContract={vi.fn()} />);
    fill("odoo-main", "shopify-store");
    expect(screen.queryByTestId("bridge-conflict-field")).toBeNull();
    fireEvent.click(screen.getByTestId("bridge-direction-two_way"));
    expect(screen.getByTestId("bridge-conflict-field")).toBeInTheDocument();
    expect(screen.getByTestId("bridge-check-conflict")).toHaveAttribute("data-status", "fail");
    expect(screen.getByTestId("bridge-flow")).toHaveAttribute("data-direction", "two_way");
    fireEvent.click(screen.getByTestId("bridge-validate-btn"));
    expect(screen.getByTestId("bridge-error-conflict")).toBeInTheDocument();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("bridge-conflict-odoo_wins")));
    fireEvent.click(screen.getByTestId("bridge-conflict-manual"));
    expect(screen.queryByTestId("bridge-error-conflict")).toBeNull();
    expect(screen.getByTestId("bridge-check-conflict")).toHaveAttribute("data-status", "pass");
  });

  it("posts the exact contract and shows a pass that claims no sync", async () => {
    const validate = vi.fn<ValidateFn>().mockResolvedValue({
      status: 200,
      body: { ok: true, tier: "I", direction: "inbound", entities: 1 },
    });
    render(<BridgeContractStudio validateContract={validate} />);
    fill("odoo-main", "shopify-store");
    fireEvent.click(screen.getByTestId("bridge-validate-btn"));
    await waitFor(() => expect(screen.getByTestId("bridge-result-passed")).toBeInTheDocument());
    expect(validate).toHaveBeenCalledWith({
      odoo_connection_id: "odoo-main",
      third_party_connection_id: "shopify-store",
      direction: "inbound",
      webhook_signature_required: true,
      entities: [{ name: "orders", money: true, money_policy: "odoo_wins" }],
    });
    expect(screen.getByTestId("bridge-result-passed-title")).toHaveTextContent("Tier I passed for inbound");
    expect(screen.getByTestId("bridge-result-passed-next")).toHaveTextContent("Nothing has synced");
    expect(screen.getByTestId("bridge-status-chip")).toHaveTextContent("Tier I passed");
    expect(screen.getByTestId("bridge-check-odoo_verified")).toHaveAttribute("data-status", "pass");
    expect(screen.getByTestId("bridge-tally")).toHaveTextContent("6/6");
    // Editing after a pass marks it stale; server rows wait again.
    fireEvent.click(screen.getByTestId("bridge-money"));
    expect(screen.getByTestId("bridge-result-stale")).toBeInTheDocument();
    expect(screen.getByTestId("bridge-status-chip")).toHaveTextContent("Edited since check");
    expect(screen.getByTestId("bridge-check-odoo_verified")).toHaveAttribute("data-status", "wait");
  });

  it("maps a server field refusal back onto the field", async () => {
    const validate = vi.fn<ValidateFn>().mockResolvedValue({
      status: 200,
      body: { ok: false, tier: "I", error: "odoo and third-party connections must differ" },
    });
    render(<BridgeContractStudio validateContract={validate} />);
    fill("odoo-main", "shopify-store");
    fireEvent.click(screen.getByTestId("bridge-validate-btn"));
    await waitFor(() => expect(screen.getByTestId("bridge-result-refused")).toBeInTheDocument());
    expect(screen.getByTestId("bridge-error-thirdId")).toHaveTextContent("different connection");
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("bridge-third-id")));
    expect(screen.getByTestId("bridge-check-odoo_verified")).toHaveAttribute("data-status", "skip");
    expect(screen.getByTestId("bridge-status-chip")).toHaveTextContent("Refused");
  });

  it("shows an honest network error and keeps entries", async () => {
    const validate = vi.fn<ValidateFn>().mockResolvedValue({ status: 502, body: null });
    render(<BridgeContractStudio validateContract={validate} />);
    fill("odoo-main", "shopify-store");
    fireEvent.click(screen.getByTestId("bridge-validate-btn"));
    await waitFor(() => expect(screen.getByTestId("bridge-result-error")).toBeInTheDocument());
    expect(screen.getByTestId("bridge-result-error-why")).toHaveTextContent("HTTP 502");
    expect(screen.getByTestId("bridge-odoo-id")).toHaveValue("odoo-main");
    expect(screen.getByTestId("bridge-status-chip")).toHaveTextContent("Unreachable");
    fireEvent.click(screen.getByTestId("bridge-retry-btn"));
    await waitFor(() => expect(validate).toHaveBeenCalledTimes(2));
  });

  it("unverified refusal fails only the named side in the ledger", () => {
    render(
      <BridgeContractStudio
        initialForm={FILLED}
        initialOutcome={classifyResult({
          ok: false,
          tier: "I",
          error: "Tier I requires verified connections (verified_at set): third_party:shopify-store (unverified)",
        })}
        validateContract={vi.fn()}
      />,
    );
    expect(screen.getByTestId("bridge-check-odoo_verified")).toHaveAttribute("data-status", "pass");
    expect(screen.getByTestId("bridge-check-third_verified")).toHaveAttribute("data-status", "fail");
    expect(screen.getByTestId("bridge-check-third_verified")).toHaveTextContent("Unverified");
  });

  it("Cmd+Enter validates from anywhere", async () => {
    const validate = vi.fn<ValidateFn>().mockResolvedValue({
      status: 200,
      body: { ok: true, tier: "I", direction: "inbound", entities: 1 },
    });
    render(<BridgeContractStudio initialForm={FILLED} validateContract={validate} />);
    fireEvent.keyDown(window, { key: "Enter", metaKey: true });
    await waitFor(() => expect(validate).toHaveBeenCalledTimes(1));
  });

  it("rejected promise becomes the error guide", async () => {
    const validate = vi.fn<ValidateFn>().mockRejectedValue(new Error("boom"));
    render(<BridgeContractStudio validateContract={validate} />);
    fill("odoo-main", "shopify-store");
    fireEvent.click(screen.getByTestId("bridge-validate-btn"));
    await waitFor(() => expect(screen.getByTestId("bridge-result-error-title")).toHaveTextContent("Could not reach Tier I"));
  });

  it("pending state disables submit and shows the checking skeleton", () => {
    render(<BridgeContractStudio initialForm={FILLED} initialPending validateContract={vi.fn()} />);
    expect(screen.getByTestId("bridge-validate-btn")).toBeDisabled();
    expect(screen.getByTestId("bridge-validate-btn")).toHaveTextContent("Validating…");
    expect(screen.getByTestId("bridge-result-pending")).toBeInTheDocument();
  });

  it("clear form resets entries and the result", () => {
    render(
      <BridgeContractStudio
        initialForm={FILLED}
        initialOutcome={classifyResult({ ok: true, tier: "I", direction: "inbound", entities: 1 })}
        validateContract={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("bridge-reset-btn"));
    expect(screen.getByTestId("bridge-odoo-id")).toHaveValue("");
    expect(screen.getByTestId("bridge-result-idle")).toBeInTheDocument();
  });
});

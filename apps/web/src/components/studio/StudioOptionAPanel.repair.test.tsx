/** @vitest-environment jsdom */
import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StudioOptionAPanel } from "./StudioOptionAPanel";
import { useStudioOptionA } from "./use-studio-option-a";
import type { StudioState } from "./use-studio-state";
import type { StudioDerived } from "./use-studio-derived";

const FAULT =
  "AttributeError: 'product.product' object has no attribute 'standard_cost'";

type Call = { url: string; body: Record<string, unknown> };

function mockFetch(status: number, payload: unknown): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url: String(url), body: JSON.parse(String(init?.body || "{}")) });
      return new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

/** Real hook + real panel; only the network is fake. */
function Harness() {
  const [session, setSession] = useState<unknown>({
    artifact: { technical_name: "x_markup", _sandbox_install: { message: FAULT } },
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [callout, setCalloutTitle] = useState<string | null>(null);
  const [note, setApplyNote] = useState<string | null>(null);
  const [fault, setLastSandboxFault] = useState<string | null>(null);
  const [validationId, setGoldValidationId] = useState<string | null>(null);
  const noop = () => undefined;
  const s = {
    session,
    connection: null,
    goldValidationId: validationId,
    goldZipBase64: null,
    goldHost: null,
    lastSandboxFault: fault,
    setSession,
    setBusy,
    setError,
    setCalloutTitle,
    setApplyNote,
    setLastSandboxFault,
    setGoldValidationId,
    setGoldZipBase64: noop,
    setGoldPromoted: noop,
    setPromoteOpen: noop,
    setInstallOpen: noop,
    setGoldHost: noop,
    setOdooAppUrl: noop,
    beginStudioAction: () => setError(null),
    failStudio: (_step: string, message: string) => setError(message),
  } as unknown as StudioState;
  const d = {
    authoredOptionA: true,
    goldOptionA: false,
    goldId: "",
    inheritHost: "sale.order",
    hostFormName: "Quotations",
  } as unknown as Pick<
    StudioDerived,
    "authoredOptionA" | "goldOptionA" | "goldId" | "inheritHost" | "hostFormName"
  >;
  const oa = useStudioOptionA("conn-1", s, d);
  return (
    <>
      <StudioOptionAPanel
        goldOptionA={false}
        authoredOptionA
        goldId=""
        goldHonesty=""
        goldSettings={null}
        goldHost={null}
        goldInspect={null}
        goldNeedsInvoicing={false}
        goldCanPromote={false}
        goldCanOpenSettings={false}
        goldPromoted={false}
        authoringPassed
        authoringRetryable={false}
        hostInstallOffers={[]}
        leftoverAuthoringFindings={[]}
        isOdooOnline={false}
        busy={busy}
        onInstallInvoicing={noop}
        onDownloadZip={noop}
        onProveSandbox={noop}
        onRepairWithAi={() => void oa.repairGoldWithAi()}
        onPromote={noop}
        onRetryAuthoring={noop}
        onReverify={noop}
        onInstallHost={noop}
      />
      <p data-testid="callout">{callout}</p>
      <p data-testid="note">{note}</p>
      <p data-testid="error">{error}</p>
      <p data-testid="fault">{fault}</p>
      <p data-testid="validation">{validationId}</p>
    </>
  );
}

async function clickRepair() {
  render(<Harness />);
  fireEvent.click(screen.getByTestId("studio-repair-with-ai"));
  await waitFor(() =>
    expect(screen.getByTestId("studio-repair-with-ai")).not.toHaveTextContent("Repairing"),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Repair with AI: post-repair states", () => {
  it("proved: stores the validation and says Promote stays human", async () => {
    const calls = mockFetch(200, {
      ok: true,
      validation_id: "val-42",
      zip_base64: "UEsDBA==",
      message: "Sandbox install & smoke passed after the AI patch. Publishing stays a step you confirm.",
      draft: { technical_name: "x_markup" },
      feedback_repair: { ok: true, applied: true, llm: true, message: "AI patched the module." },
    });
    await clickRepair();
    await waitFor(() =>
      expect(screen.getByTestId("callout")).toHaveTextContent("Sandbox proved after AI repair"),
    );
    expect(screen.getByTestId("validation")).toHaveTextContent("val-42");
    expect(screen.getByTestId("note")).toHaveTextContent("Publishing stays a step you confirm");
    expect(screen.getByTestId("error")).toBeEmptyDOMElement();
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("/api/connections/conn-1/module-spec/option-a-repair-feedback");
    expect(calls[0].body).toMatchObject({ error_text: FAULT, retry_sandbox: true });
  });

  it("still failing: shows the new sandbox Fault, not the upbeat repair note", async () => {
    mockFetch(200, {
      ok: false,
      message: "KeyError: 'x_markup_amount'",
      draft: { technical_name: "x_markup" },
      feedback_repair: {
        ok: true,
        applied: true,
        llm: true,
        message: "AI patched the module from the sandbox error. Retry Sandbox install & smoke.",
      },
    });
    await clickRepair();
    await waitFor(() =>
      expect(screen.getByTestId("error")).toHaveTextContent(
        "The AI patch applied, but the sandbox still fails: KeyError: 'x_markup_amount'",
      ),
    );
    expect(screen.getByTestId("fault")).toHaveTextContent("KeyError: 'x_markup_amount'");
    expect(screen.getByTestId("callout")).toHaveTextContent("AI patched the module");
    expect(screen.getByTestId("validation")).toBeEmptyDOMElement();
  });

  it("budget used: shows the honest budget copy and no patch callout", async () => {
    const budget =
      "LLM Repair budget for this draft is used up. Try Sandbox install & smoke once more. " +
      "Or Download module zip / Start a new app for a fresh LLM repair budget. Do not click Install this app.";
    mockFetch(200, {
      ok: false,
      message: budget,
      draft: { technical_name: "x_markup" },
      feedback_repair: { ok: false, applied: false, reason: "max_repair_exceeded", message: budget },
    });
    await clickRepair();
    await waitFor(() => expect(screen.getByTestId("error")).toHaveTextContent("budget for this draft is used up"));
    expect(screen.getByTestId("error")).toHaveTextContent("Download module zip");
    expect(screen.getByTestId("callout")).toBeEmptyDOMElement();
    expect(screen.getByTestId("fault")).toBeEmptyDOMElement();
  });

  it("Odoo Online refusal from the API reaches the operator", async () => {
    mockFetch(409, {
      detail:
        "Repair with AI is not available on Odoo Online. Move this app to Odoo.sh or a self-hosted server.",
    });
    await clickRepair();
    await waitFor(() =>
      expect(screen.getByTestId("error")).toHaveTextContent("not available on Odoo Online"),
    );
    expect(screen.getByTestId("callout")).toBeEmptyDOMElement();
  });
});

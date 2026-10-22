/** @vitest-environment happy-dom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import CodeStudioPage from "./page";

const mocks = vi.hoisted(() => ({
  getConnection: vi.fn(),
  getCodeStudioGate: vi.fn(),
  listModels: vi.fn(),
  getCodeStudioContext: vi.fn(),
  getCodeStudioSnippets: vi.fn(),
  getProductionReadiness: vi.fn(),
  validateCodeStudio: vi.fn(),
  testRunCodeStudio: vi.fn(),
  bindCodeStudio: vi.fn(),
  exportCodeStudioOptionA: vi.fn(),
  probeCodeStudio: vi.fn(),
}));

vi.mock("@/components/code-studio/code-studio-operate.css", () => ({}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "conn-1" }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/lib/api", () => {
  class ConfirmationRequiredError extends Error {
    risks: string[] = [];
    warning = "";
    confirm_phrase = "I understand the risks";
    status = 403;
  }
  return {
    ConfirmationRequiredError,
    api: mocks,
  };
});

const VALID = { ok: true, syntax_ok: true, warnings: [], error: null, line: null };

function readyGate({ supported = true }: { supported?: boolean } = {}) {
  mocks.getConnection.mockResolvedValue({
    id: "conn-1",
    name: "Dev",
    write_mode: "standard",
    server_version: "19.0",
  });
  mocks.getCodeStudioGate.mockResolvedValue({
    probe: { supported },
    gating: {
      feature: "code_studio",
      title: supported ? "Live code server actions" : "Live code actions unavailable",
      why: supported
        ? "This instance accepts state=code server actions via RPC."
        : "Live code actions are not available on this instance.",
      options: supported ? [] : ["Export Python as an installable module (custom code)"],
      available: supported,
      capability_key: "code_server_actions",
      gating_choices: [],
    },
    developer_role_required: true,
    entitlement_key: "dev_tools",
  });
  mocks.listModels.mockResolvedValue([
    { id: 1, model: "res.partner", name: "Contact", state: "base", transient: false },
  ]);
  mocks.getCodeStudioContext.mockResolvedValue({
    major: 19,
    symbols: [{ name: "records", description: "Recordset the action runs on." }],
  });
  mocks.getCodeStudioSnippets.mockResolvedValue({ snippets: [] });
  mocks.getProductionReadiness.mockResolvedValue({ first_write_acknowledged: true });
  mocks.validateCodeStudio.mockResolvedValue(VALID);
}

async function validate() {
  fireEvent.click(screen.getByRole("button", { name: "Validate code" }));
  await screen.findByText("Validated. The authoring gate passed.");
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Code Studio page", () => {
  it("states both limits, keeps the Option A warning, and highlights a blocked import", async () => {
    readyGate();
    render(<CodeStudioPage />);

    expect(await screen.findByTestId("code-studio-limit-live")).toHaveTextContent(
      "instance probe",
    );
    expect(screen.getByTestId("code-studio-limit-live")).toHaveTextContent("confirm phrase");
    expect(screen.getByTestId("code-studio-limit-live")).toHaveTextContent("snapshot");
    expect(screen.getByTestId("code-studio-limit-option-a")).toHaveTextContent("does not install");
    expect(screen.getByTestId("code-studio-limit-option-a")).toHaveTextContent("does not publish it");
    expect(screen.getByTestId("code-studio-option-a-warning")).toHaveTextContent(
      "Never installs from here",
    );
    expect(screen.getByTestId("code-studio-option-a-warning")).toHaveTextContent("A person promotes it");

    const editor = await screen.findByTestId("code-studio-editor");
    expect(editor.querySelector("textarea")).toBeNull();

    fireEvent.change(screen.getByLabelText("Line 1"), { target: { value: "import os" } });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("imports_forbidden");
    expect(editor.querySelector(".token")).not.toBeNull();
  });

  it("makes Validate the only filled primary action", async () => {
    readyGate();
    render(<CodeStudioPage />);
    const validateButton = await screen.findByRole("button", { name: "Validate code" });
    const primaries = Array.from(document.querySelectorAll("button.bg-accent"));
    expect(primaries).toEqual([validateButton]);
  });

  it("never offers live bind before the authoring gate passes, and voids the pass on edit", async () => {
    readyGate();
    render(<CodeStudioPage />);
    await screen.findByTestId("code-studio-editor");

    const bind = screen.getByRole("button", { name: "Bind live action" });
    expect(bind).toBeDisabled();
    expect(screen.getByTestId("code-studio-bind-block")).toHaveTextContent("Validate this code first.");
    expect(screen.getByRole("button", { name: "Test run on record" })).toBeDisabled();

    await validate();
    expect(mocks.validateCodeStudio).toHaveBeenCalledWith("conn-1", expect.stringContaining("records"));
    expect(screen.getByRole("button", { name: "Bind live action" })).toBeEnabled();
    expect(screen.getByTestId("code-studio-gate-pill")).toHaveTextContent("Validated");

    fireEvent.change(screen.getByLabelText("Line 2"), { target: { value: "    rec.write({})" } });
    expect(await screen.findByTestId("code-studio-stale")).toHaveTextContent(
      "This code changed. Validate again.",
    );
    expect(screen.getByRole("button", { name: "Bind live action" })).toBeDisabled();
    expect(screen.getByTestId("code-studio-bind-block")).toHaveTextContent(
      "This code changed. Validate again.",
    );
    expect(mocks.bindCodeStudio).not.toHaveBeenCalled();
  });

  it("keeps bind off when Validate finds a blocked rule", async () => {
    readyGate();
    mocks.validateCodeStudio.mockResolvedValue({
      ...VALID,
      warnings: [{ code: "sudo_pattern", message: "sudo is blocked.", line: "2" }],
    });
    render(<CodeStudioPage />);
    await screen.findByTestId("code-studio-editor");
    fireEvent.click(screen.getByRole("button", { name: "Validate code" }));
    expect(await screen.findByText("Blocked on the server-action path")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bind live action" })).toBeDisabled();
  });

  it("keeps bind off after a failed test and shows the snapshot id", async () => {
    readyGate();
    mocks.testRunCodeStudio.mockResolvedValue({
      ok: false,
      validation: VALID,
      ran_for_real: true,
      record: { model: "res.partner", id: null },
      exception: "boom",
      field_diff: [],
      snapshot_id: "snap-99",
    });
    render(<CodeStudioPage />);
    await screen.findByTestId("code-studio-editor");
    await validate();
    fireEvent.click(screen.getByRole("button", { name: "Test run on record" }));
    expect(await screen.findByTestId("code-studio-test-result")).toHaveTextContent("snap-99");
    expect(screen.getByRole("button", { name: "Bind live action" })).toBeDisabled();
    expect(screen.getByTestId("code-studio-bind-block")).toHaveTextContent("snap-99");
    expect(mocks.bindCodeStudio).not.toHaveBeenCalled();
  });

  it("opens the confirm dialog before any bind request", async () => {
    readyGate();
    render(<CodeStudioPage />);
    await screen.findByTestId("code-studio-editor");
    await validate();
    fireEvent.click(screen.getByRole("button", { name: "Bind live action" }));
    expect(await screen.findByTestId("confirm-dialog-v2")).toBeInTheDocument();
    expect(mocks.bindCodeStudio).not.toHaveBeenCalled();
  });

  it("locks the Option A zip until Validate, and keeps the no-install limit on that path", async () => {
    readyGate();
    render(<CodeStudioPage />);
    await screen.findByTestId("code-studio-editor");
    fireEvent.click(screen.getByRole("radio", { name: "Custom-code module" }));
    expect(await screen.findByTestId("code-studio-option-a")).toHaveTextContent(
      "Nothing is installed",
    );
    expect(screen.getByRole("button", { name: "Download module zip" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Bind live action" })).not.toBeInTheDocument();
    await validate();
    expect(screen.getByRole("button", { name: "Download module zip" })).toBeEnabled();
  });

  it("opens on the Option A path when the probe refuses live code", async () => {
    readyGate({ supported: false });
    render(<CodeStudioPage />);
    expect(await screen.findByTestId("gating-callout")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: "Custom-code module" })).toBeChecked(),
    );
    expect(screen.getByTestId("code-studio-option-a-warning")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Bind live action" })).not.toBeInTheDocument();
  });

  it("hides a raw traceback behind Show details", async () => {
    readyGate();
    const toastMessages: string[] = [];
    const onApiError = (event: Event) => {
      toastMessages.push((event as CustomEvent<{ message?: string }>).detail?.message ?? "");
    };
    window.addEventListener("app:api-error", onApiError);
    mocks.getCodeStudioContext.mockRejectedValue(
      new Error(
        [
          "Authentication RPC failed",
          "Traceback (most recent call last):",
          '  File "/usr/lib/python3/dist-packages/odoo/service/db.py", line 1',
          'psycopg.OperationalError: database "granted" does not exist',
        ].join("\n"),
      ),
    );
    try {
      render(<CodeStudioPage />);

      expect(await screen.findByTestId("code-studio-limit-live")).toBeInTheDocument();
      expect(screen.getByTestId("code-studio-limit-option-a")).toBeInTheDocument();

      const notice = await screen.findByTestId("error-notice");
      expect(screen.getByTestId("error-notice-message")).toHaveTextContent(
        "The connection database is not reachable.",
      );
      expect(notice).not.toHaveTextContent("psycopg");
      expect(notice).not.toHaveTextContent("Traceback");
      expect(notice).not.toHaveTextContent('database "granted" does not exist');
      expect(screen.queryByTestId("error-notice-details")).not.toBeInTheDocument();

      expect(toastMessages).toEqual(["The connection database is not reachable."]);
      expect(toastMessages.join("\n")).not.toMatch(
        /Authentication RPC failed|psycopg|Traceback|database "granted" does not exist/,
      );

      fireEvent.click(screen.getByRole("button", { name: "Show details" }));
      const details = await screen.findByTestId("error-notice-details");
      expect(details).toHaveTextContent("psycopg");
      expect(details).toHaveTextContent("Traceback");
      expect(details).toHaveTextContent('database "granted" does not exist');
    } finally {
      window.removeEventListener("app:api-error", onApiError);
    }
  });
});

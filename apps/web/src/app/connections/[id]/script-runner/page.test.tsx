/** @vitest-environment happy-dom */
import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ScriptRunnerPage from "./page";

const mocks = vi.hoisted(() => ({
  getConnection: vi.fn(),
  getScriptRunnerTemplates: vi.fn(),
  listScriptRuns: vi.fn(),
  listSavedScripts: vi.fn(),
  getProductionReadiness: vi.fn(),
  ackProductionFirstWrite: vi.fn(),
  runScript: vi.fn(),
  getJob: vi.fn(),
  cancelJob: vi.fn(),
  saveScript: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "conn-1" }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/script-runner/script-runner-operate.css", () => ({}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() },
}));

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: vi.fn(),
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

function readyConnection() {
  mocks.getConnection.mockResolvedValue({
    id: "conn-1",
    name: "Dev",
    write_mode: "standard",
    server_version: "19.0",
  });
  mocks.getScriptRunnerTemplates.mockResolvedValue({ templates: [] });
  mocks.listSavedScripts.mockResolvedValue([]);
  mocks.getProductionReadiness.mockResolvedValue({ first_write_acknowledged: true });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Script Runner page", () => {
  it("shows honesty, empty last run, and a highlighted editor", async () => {
    readyConnection();
    mocks.listScriptRuns.mockResolvedValue([]);
    render(<ScriptRunnerPage />);

    expect(await screen.findByTestId("script-runner-honesty")).toHaveTextContent(/no [Tt]est run/i);
    expect(screen.getByTestId("script-runner-limits")).toHaveTextContent("filesystem");
    expect(screen.getByTestId("script-runner-limits")).toHaveTextContent("confirm phrase");
    expect(screen.getByTestId("script-runner-stage-rail")).toBeInTheDocument();
    expect(screen.queryByTestId("script-runner-step-dry-run")).toBeNull();
    expect(screen.getByTestId("script-runner-step-compose")).toBeInTheDocument();
    expect(screen.getByTestId("script-runner-step-confirm")).toBeInTheDocument();
    expect(screen.getByTestId("script-runner-step-run")).toBeInTheDocument();
    expect(await screen.findByText("No run yet")).toBeInTheDocument();
    const editor = screen.getByTestId("script-runner-editor");
    expect(editor.querySelector("textarea")).toBeNull();
    expect(editor.querySelector(".token")).not.toBeNull();
    expect(screen.getByTestId("script-runner-run-btn")).toHaveTextContent("Run script");
  });

  it("opens the confirm dialog before any run request", async () => {
    readyConnection();
    mocks.listScriptRuns.mockResolvedValue([]);
    render(<ScriptRunnerPage />);
    await screen.findByTestId("script-runner-editor");
    fireEvent.click(screen.getByTestId("script-runner-run-btn"));
    expect(await screen.findByTestId("confirm-dialog-v2")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-dialog-v2")).toHaveTextContent(/no [Tt]est run/i);
    expect(mocks.runScript).not.toHaveBeenCalled();
  });

  it("shows the last failure and how to restore the snapshot", async () => {
    readyConnection();
    mocks.listScriptRuns.mockResolvedValue([
      {
        id: "run-1",
        status: "failed",
        script_hash: "abc123abc123abc123",
        script_content: "odoo.execute_kw('res.partner', 'write', [[1], {}])",
        stdout: "",
        stderr: "boom",
        write_counts: {},
        write_count: 0,
        error: "boom",
        snapshot_id: "snap-77",
        created_at: "2026-10-04T00:00:00Z",
      },
    ]);
    render(<ScriptRunnerPage />);
    expect(await screen.findByTestId("script-runner-failure")).toHaveTextContent("boom");
    const restore = screen.getByTestId("script-runner-restore");
    expect(restore).toHaveTextContent("snap-77");
    expect(restore).toHaveTextContent("does not undo record writes");
    expect(restore).toHaveTextContent("Dropped columns cannot be restored");
    expect(screen.getByRole("link", { name: "Open the journal" })).toHaveAttribute(
      "href",
      "/connections/conn-1/journal",
    );
    expect(screen.getByTestId("script-runner-result-label")).toHaveTextContent(/run result/i);
  });

  it("flags a forbidden import beside the line and confirms a finished run", async () => {
    readyConnection();
    mocks.listScriptRuns
      .mockResolvedValueOnce([])
      .mockResolvedValue([
        {
          id: "run-2",
          status: "succeeded",
          script_hash: "def456def456def456",
          script_content: "log('ok')",
          stdout: "ok",
          stderr: null,
          write_counts: {},
          write_count: 0,
          error: null,
          snapshot_id: null,
          created_at: "2026-10-04T00:00:00Z",
        },
      ]);
    mocks.runScript.mockResolvedValue({ ok: true, async: true, job_id: "job-1", run_id: "run-2" });
    mocks.getJob.mockResolvedValue({
      id: "job-1",
      status: "succeeded",
      result: { ok: true, stdout: "ok", write_counts: {} },
    });
    render(<ScriptRunnerPage />);
    await screen.findByTestId("script-runner-editor");
    fireEvent.change(screen.getByLabelText("Line 1"), { target: { value: "import socket" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("not available");

    fireEvent.click(screen.getByTestId("script-runner-run-btn"));
    const input = await screen.findByTestId("confirm-dialog-v2-input");
    fireEvent.change(input, { target: { value: "I understand the risks" } });
    fireEvent.click(screen.getByTestId("confirm-dialog-v2-confirm"));
    expect(await screen.findByTestId("script-runner-success")).toHaveTextContent(/No writes were recorded/i);
    expect(mocks.runScript).toHaveBeenCalledWith(
      "conn-1",
      expect.objectContaining({ confirm_phrase: "I understand the risks" }),
    );
  });

  it("shows observer honesty and disables Run script", async () => {
    mocks.getConnection.mockResolvedValue({
      id: "conn-1",
      name: "Dev",
      write_mode: "observer",
      server_version: "19.0",
    });
    mocks.getScriptRunnerTemplates.mockResolvedValue({ templates: [] });
    mocks.listSavedScripts.mockResolvedValue([]);
    mocks.listScriptRuns.mockResolvedValue([]);
    mocks.getProductionReadiness.mockResolvedValue({ first_write_acknowledged: true });
    render(<ScriptRunnerPage />);
    expect(await screen.findByTestId("script-runner-observer")).toHaveTextContent(/observer/i);
    expect(screen.getByTestId("script-runner-run-btn")).toBeDisabled();
  });
});

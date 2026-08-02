import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ConfirmationRequiredError } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ConfirmationRequiredError parsing", () => {
  it("throws ConfirmationRequiredError when detail.requires_confirmation is true", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          {
            detail: {
              requires_confirmation: true,
              warning: "Live Python is risky",
              risks: ["Can destroy data", "Hard to audit"],
              confirm_phrase: "I understand the risks",
            },
          },
          { status: 403 },
        ),
      ),
    );

    await expect(
      api.deleteAutomation("conn-1", 42, { confirm_advanced: false }),
    ).rejects.toBeInstanceOf(ConfirmationRequiredError);

    try {
      await api.deleteAutomation("conn-1", 42, { confirm_advanced: false });
    } catch (err) {
      expect(err).toBeInstanceOf(ConfirmationRequiredError);
      const cre = err as ConfirmationRequiredError;
      expect(cre.warning).toBe("Live Python is risky");
      expect(cre.risks).toEqual(["Can destroy data", "Hard to audit"]);
      expect(cre.confirm_phrase).toBe("I understand the risks");
      expect(cre.requires_confirmation).toBe(true);
      expect(cre.message).toBe("Live Python is risky");
    }
  });

  it("throws plain Error for non-confirmation failures with string detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({ detail: "Connection not found" }, { status: 404 }),
      ),
    );

    await expect(api.listConnections()).rejects.toThrow("Connection not found");
    await expect(api.listConnections()).rejects.not.toBeInstanceOf(
      ConfirmationRequiredError,
    );
  });

  it("preserves structured message from object detail without requires_confirmation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          { detail: { message: "Invalid model name", code: "bad_model" } },
          { status: 400 },
        ),
      ),
    );

    await expect(api.listModels("conn-1")).rejects.toThrow("Invalid model name");
  });
});

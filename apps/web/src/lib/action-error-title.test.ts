import { describe, expect, it } from "vitest";
import { actionErrorTitle } from "./action-error-title";

const TITLES = {
  zip: "Zip export failed",
  sandbox: "Sandbox prove failed",
  repair: "AI repair did not apply",
} as const;

describe("actionErrorTitle", () => {
  it("titles from the failed action key, never from scanning the body", () => {
    expect(
      actionErrorTitle(
        "repair",
        TITLES,
        "Request failed",
        "Repair budget exhausted. Promote the last passing zip.",
      ),
    ).toBe("AI repair did not apply");
    expect(actionErrorTitle("zip", TITLES, "Request failed", "anything")).toBe("Zip export failed");
  });

  it("never infers zip from the word zip in untagged copy", () => {
    expect(
      actionErrorTitle(
        "Repair budget exhausted or artifacts are locked after a passing sandbox. Start a new app or Promote the last passing zip.",
        TITLES,
        "Request failed",
      ),
    ).toBe("Request failed");
  });
});

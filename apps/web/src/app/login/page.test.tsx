/** @vitest-environment jsdom */
import React from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const push = vi.fn();
let searchParams = new URLSearchParams();
const accountLogin = vi.fn();
const accountOAuthComplete2FA = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => searchParams,
}));

vi.mock("@/lib/api", () => ({
  api: {
    accountLogin: (...args: unknown[]) => accountLogin(...args),
    accountOAuthComplete2FA: (...args: unknown[]) => accountOAuthComplete2FA(...args),
  },
}));

vi.mock("@/components/auth/OAuthProviderButtons", () => ({
  OAuthProviderButtons: () => null,
}));

import LoginPage from "@/app/login/page";

beforeAll(() => {
  if (typeof document.elementFromPoint !== "function") {
    document.elementFromPoint = () => null;
  }
});

beforeEach(() => {
  push.mockReset();
  accountLogin.mockReset().mockResolvedValue({});
  accountOAuthComplete2FA.mockReset().mockResolvedValue({});
  searchParams = new URLSearchParams();
});

afterEach(() => {
  cleanup();
});

function codeInput() {
  return screen.getByLabelText("Two-factor code") as HTMLInputElement;
}

function typeCode(value: string) {
  const input = codeInput();
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value } });
}

function fillCredentials() {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ops@example.com" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "s3cret-pass" } });
}

describe("LoginPage two-factor step", () => {
  it("renders the shared OTP field with one-time-code autocomplete", () => {
    render(<LoginPage />);
    const input = codeInput();
    expect(input).toHaveAttribute("autocomplete", "one-time-code");
    expect(input).toHaveAttribute("inputmode", "numeric");
    expect(input).not.toBeRequired();
  });

  it("signs in without a code when two-factor is off", async () => {
    render(<LoginPage />);
    fillCredentials();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(accountLogin).toHaveBeenCalledWith({ email: "ops@example.com", password: "s3cret-pass" }),
    );
    expect(push).toHaveBeenCalledWith("/connect");
  });

  it("sends a full 6-digit code with the password login", async () => {
    render(<LoginPage />);
    fillCredentials();
    typeCode("123456");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(accountLogin).toHaveBeenCalledWith({
        email: "ops@example.com",
        password: "s3cret-pass",
        totp_code: "123456",
      }),
    );
  });

  it("blocks a partial code with a one-sentence error and no API call", async () => {
    render(<LoginPage />);
    fillCredentials();
    typeCode("123");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter all 6 digits of the code from your authenticator app.",
    );
    expect(codeInput()).toHaveAttribute("aria-invalid", "true");
    expect(accountLogin).not.toHaveBeenCalled();
  });

  it("enables Complete sign-in only once 6 digits are entered in the OAuth step", async () => {
    searchParams = new URLSearchParams("oauth_totp=1&token=oauth-token");
    render(<LoginPage />);
    expect(screen.queryByLabelText("Email")).toBeNull();
    expect(codeInput()).toBeRequired();
    const submit = screen.getByRole("button", { name: "Complete sign-in" });
    expect(submit).toBeDisabled();

    typeCode("654321");
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.click(submit);
    await waitFor(() =>
      expect(accountOAuthComplete2FA).toHaveBeenCalledWith({
        token: "oauth-token",
        totp_code: "654321",
      }),
    );
    expect(push).toHaveBeenCalledWith("/connect");
  });

  it("disables the code field while verifying", async () => {
    searchParams = new URLSearchParams("oauth_totp=1&token=oauth-token");
    let resolveLogin: () => void = () => {};
    accountOAuthComplete2FA.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveLogin = resolve;
      }),
    );
    render(<LoginPage />);
    typeCode("654321");
    fireEvent.click(await screen.findByRole("button", { name: "Complete sign-in" }));
    await waitFor(() => expect(codeInput()).toBeDisabled());
    expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled();
    resolveLogin();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/connect"));
  });
});

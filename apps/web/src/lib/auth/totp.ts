export const TOTP_CODE_LENGTH = 6;

/** Keeps the digits of a pasted code so "123 456" or "123-456" fills all slots. */
export function normalizeTotpPaste(raw: string): string {
  return raw.replace(/\D/g, "").slice(0, TOTP_CODE_LENGTH);
}

export function isCompleteTotpCode(code: string): boolean {
  return code.length === TOTP_CODE_LENGTH && /^\d+$/.test(code);
}

/** Returns a one-sentence error for a code that cannot be submitted, or null when it can. */
export function totpCodeError(code: string, required: boolean): string | null {
  if (code.length === 0) {
    return required ? "Enter the 6-digit code from your authenticator app." : null;
  }
  if (!isCompleteTotpCode(code)) {
    return "Enter all 6 digits of the code from your authenticator app.";
  }
  return null;
}

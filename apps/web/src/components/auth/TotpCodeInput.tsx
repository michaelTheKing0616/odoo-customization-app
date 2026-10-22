"use client";

import { useId } from "react";
import { OTPInput, REGEXP_ONLY_DIGITS, type SlotProps } from "input-otp";
import { cn } from "@/lib/cn";
import { TOTP_CODE_LENGTH, normalizeTotpPaste } from "@/lib/auth/totp";

export type TotpCodeInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Called once all 6 digits are entered (typed, pasted, or filled by a password manager). */
  onComplete?: (value: string) => void;
  description?: string;
  /** One sentence. Marks the field invalid and is announced to screen readers. */
  error?: string | null;
  required?: boolean;
  disabled?: boolean;
  /** True while the code is being verified; disables the field and sets aria-busy. */
  busy?: boolean;
  autoFocus?: boolean;
  id?: string;
};

type TotpSlotProps = SlotProps & { invalid: boolean; inactive: boolean };

function TotpSlot({ char, isActive, hasFakeCaret, invalid, inactive }: TotpSlotProps) {
  return (
    <div
      className={cn(
        "relative flex h-10 w-10 items-center justify-center rounded-md border bg-surface text-base font-medium tabular-nums text-ink",
        invalid ? "border-danger" : "border-border-subtle",
        isActive && !inactive && "z-10 ring-2 ring-offset-2",
        isActive && !inactive && (invalid ? "ring-danger" : "ring-accent"),
        inactive && "opacity-60",
      )}
      aria-hidden
      data-slot="totp-slot"
    >
      {char}
      {hasFakeCaret && !inactive ? (
        <div className="pointer-events-none absolute inset-y-2 flex items-center">
          <div className="h-5 w-px bg-ink motion-safe:animate-pulse" />
        </div>
      ) : null}
    </div>
  );
}

export function TotpCodeInput({
  label,
  value,
  onChange,
  onComplete,
  description,
  error,
  required,
  disabled,
  busy = false,
  autoFocus,
  id,
}: TotpCodeInputProps) {
  const generatedId = useId();
  const inputId = id ?? `totp-${generatedId}`;
  const descriptionId = description ? `${inputId}-description` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;
  const inactive = Boolean(disabled || busy);

  return (
    <div className="space-y-1 text-sm" aria-busy={busy || undefined}>
      <label htmlFor={inputId} className="block">
        {label}
      </label>
      {description ? (
        <p id={descriptionId} className="text-xs text-muted">
          {description}
        </p>
      ) : null}
      <OTPInput
        id={inputId}
        maxLength={TOTP_CODE_LENGTH}
        value={value}
        onChange={onChange}
        onComplete={onComplete}
        pattern={REGEXP_ONLY_DIGITS}
        pasteTransformer={normalizeTotpPaste}
        inputMode="numeric"
        autoComplete="one-time-code"
        required={required}
        disabled={inactive}
        autoFocus={autoFocus}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        containerClassName="flex items-center gap-2 has-[:disabled]:cursor-not-allowed"
        render={({ slots }) => (
          <>
            {slots.map((slot, idx) => (
              <TotpSlot key={idx} {...slot} invalid={Boolean(error)} inactive={inactive} />
            ))}
          </>
        )}
      />
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

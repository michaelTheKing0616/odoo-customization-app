"use client";

import { OTPInput, REGEXP_ONLY_DIGITS, type SlotProps } from "input-otp";
import { cn } from "@/lib/cn";

export type TotpCodeInputProps = {
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  disabled?: boolean;
  id?: string;
};

function TotpSlot({ char, isActive, hasFakeCaret }: SlotProps) {
  return (
    <div
      className={cn(
        "relative flex h-9 w-9 items-center justify-center rounded-md border border-border-subtle bg-surface text-sm font-medium tabular-nums text-ink",
        isActive && "z-10 ring-2 ring-accent ring-offset-2",
      )}
      aria-hidden
    >
      {char}
      {hasFakeCaret ? (
        <div className="pointer-events-none absolute inset-y-2 flex items-center">
          <div className="h-4 w-px bg-ink" />
        </div>
      ) : null}
    </div>
  );
}

export function TotpCodeInput({
  value,
  onChange,
  required,
  disabled,
  id,
}: TotpCodeInputProps) {
  return (
    <OTPInput
      id={id}
      maxLength={6}
      value={value}
      onChange={onChange}
      pattern={REGEXP_ONLY_DIGITS}
      inputMode="numeric"
      autoComplete="one-time-code"
      required={required}
      disabled={disabled}
      containerClassName="flex items-center gap-2"
      render={({ slots }) => (
        <>
          {slots.map((slot, idx) => (
            <TotpSlot key={idx} {...slot} />
          ))}
        </>
      )}
    />
  );
}

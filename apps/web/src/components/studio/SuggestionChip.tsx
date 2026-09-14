"use client";

type SuggestionChipProps = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  selected?: boolean;
};

export function SuggestionChip({ label, onClick, disabled, selected }: SuggestionChipProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`chip ${selected ? "is-selected" : ""}`}
    >
      {label}
    </button>
  );
}

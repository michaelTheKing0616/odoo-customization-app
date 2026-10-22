import type { CrudPermits } from "@/lib/accessForm";
import { PERM_COLUMNS } from "@/lib/accessScreen";

/** R W C D as four quiet letters; granted ones carry the teal accent. */
export function AccessCrudLetters({ value, testId }: { value: CrudPermits; testId?: string }) {
  const granted = PERM_COLUMNS.filter((c) => value[c.key]).map((c) => c.label);
  return (
    <span
      className="ax-crud"
      data-testid={testId}
      aria-label={granted.length ? `Grants ${granted.join(", ")}` : "Grants nothing"}
      role="img"
    >
      {PERM_COLUMNS.map((c) => (
        <span key={c.key} data-on={value[c.key] ? "true" : "false"} aria-hidden>
          {c.letter}
        </span>
      ))}
    </span>
  );
}

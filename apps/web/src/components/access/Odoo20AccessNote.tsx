import {
  accessScreenBranch,
  ODOO20_COMBINED_ACCESS_NOTE,
} from "@/lib/accessMajor";

type Odoo20AccessNoteProps = {
  major: number | null | undefined;
};

/** Inline major-20 note. Hidden on 19 and below. Does not mention Studio. */
export function Odoo20AccessNote({ major }: Odoo20AccessNoteProps) {
  const branch = accessScreenBranch(major);
  if (!branch.note) return null;
  return (
    <p className="mt-2 text-sm text-muted" data-testid="odoo20-access-note">
      {ODOO20_COMBINED_ACCESS_NOTE}
    </p>
  );
}

"use client";

import { Badge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import {
  expertCautionDescription,
  expertCautionTone,
  formatExpertCautionFlag,
} from "@/lib/expert-caution-flags";

type ExpertCautionFlagsProps = {
  flags: string[];
};

export function ExpertCautionFlags({ flags }: ExpertCautionFlagsProps) {
  const rows = flags
    .map((flag) => {
      const label = formatExpertCautionFlag(flag);
      if (!label) return null;
      return {
        flag,
        label,
        tone: expertCautionTone(flag),
        body: expertCautionDescription(flag),
      };
    })
    .filter((row): row is NonNullable<typeof row> => Boolean(row));

  if (rows.length === 0) return null;

  const callouts = rows.filter((row) => row.body);
  const tone = rows.some((row) => row.tone === "danger") ? "danger" : "warning";

  return (
    <div className="expert-caution-stack" data-testid="expert-caution-flags">
      <div className="flex flex-wrap gap-1.5">
        {rows.map((row) => (
          <Badge key={row.flag} variant={row.tone === "danger" ? "danger" : "warning"}>
            {row.label}
          </Badge>
        ))}
      </div>
      {callouts.length > 0 ? (
        <Callout
          variant={tone === "danger" ? "danger" : "warning"}
          title={callouts.length === 1 ? callouts[0]!.label : "Read before you act"}
          className="expert-caution-callout"
        >
          {callouts.length === 1 ? (
            callouts[0]!.body
          ) : (
            <ul className="list-disc space-y-1 pl-4">
              {callouts.map((row) => (
                <li key={row.flag}>
                  <span className="font-medium text-ink">{row.label}.</span> {row.body}
                </li>
              ))}
            </ul>
          )}
        </Callout>
      ) : null}
    </div>
  );
}

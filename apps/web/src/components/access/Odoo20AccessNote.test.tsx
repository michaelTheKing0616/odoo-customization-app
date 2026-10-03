/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  accessScreenBranch,
  invokeRecordRuleCreate,
  ODOO20_COMBINED_ACCESS_NOTE,
  shouldOfferRecordRuleCreate,
} from "@/lib/accessMajor";
import { Odoo20AccessNote } from "./Odoo20AccessNote";

afterEach(() => cleanup());

function AccessMajorFixture({
  major,
  onCreateRule,
}: {
  major: number;
  onCreateRule: () => void;
}) {
  const branch = accessScreenBranch(major);
  return (
    <div>
      <Odoo20AccessNote major={major} />
      {branch.offerRecordRuleCreate ? (
        <button
          type="button"
          data-testid="access-new-rule"
          onClick={() => {
            invokeRecordRuleCreate(major, onCreateRule);
          }}
        >
          New rule
        </button>
      ) : null}
    </div>
  );
}

describe("Odoo20AccessNote / access major branch", () => {
  it("major 20 shows the note and does not call the record-rule create", () => {
    const onCreateRule = vi.fn();
    render(<AccessMajorFixture major={20} onCreateRule={onCreateRule} />);

    expect(screen.getByTestId("odoo20-access-note")).toHaveTextContent(
      ODOO20_COMBINED_ACCESS_NOTE,
    );
    expect(screen.queryByTestId("access-new-rule")).not.toBeInTheDocument();
    expect(shouldOfferRecordRuleCreate(20)).toBe(false);
    expect(invokeRecordRuleCreate(20, onCreateRule)).toBe(false);
    expect(onCreateRule).not.toHaveBeenCalled();
    expect(accessScreenBranch(20).fetchRecordRules).toBe(false);
  });

  it("major 19 does not show that note and keeps the existing rule action", () => {
    const onCreateRule = vi.fn();
    render(<AccessMajorFixture major={19} onCreateRule={onCreateRule} />);

    expect(screen.queryByTestId("odoo20-access-note")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("access-new-rule"));
    expect(onCreateRule).toHaveBeenCalledTimes(1);
    expect(shouldOfferRecordRuleCreate(19)).toBe(true);
    expect(accessScreenBranch(19).note).toBeNull();
    expect(accessScreenBranch(19).fetchRecordRules).toBe(true);
  });
});

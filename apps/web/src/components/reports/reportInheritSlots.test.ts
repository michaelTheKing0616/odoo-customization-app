import { describe, expect, it } from "vitest";
import {
  DEFAULT_INHERIT_SLOT,
  REPORT_INHERIT_SLOTS,
  RT22_ROOT_REPLACE_MESSAGE,
  buildReportInheritOp,
  inheritAnchorForSlot,
  parseInheritSlotFromArch,
  reportInheritRootReplaceIssue,
  slotFromXpathPosition,
} from "./reportInheritSlots";

describe("PDF-03 report inherit slots", () => {
  it("maps each slot to a single xpath and non-replace position", () => {
    expect(REPORT_INHERIT_SLOTS).toHaveLength(4);
    const bySlot = Object.fromEntries(
      REPORT_INHERIT_SLOTS.map((s) => [s.slot, s]),
    );
    expect(bySlot.header).toMatchObject({
      xpath: "//div[@class='header']",
      position: "inside",
    });
    expect(bySlot.before_body).toMatchObject({
      xpath: "//div[@class='page']",
      position: "before",
    });
    expect(bySlot.after_body).toMatchObject({
      xpath: "//div[@class='page']",
      position: "after",
    });
    expect(bySlot.footer).toMatchObject({
      xpath: "//div[@class='footer']",
      position: "inside",
    });
    for (const entry of REPORT_INHERIT_SLOTS) {
      expect(entry.position).not.toBe("replace");
    }
  });

  it("buildReportInheritOp emits report.inherit with exactly one anchor", () => {
    const built = buildReportInheritOp({
      baseReportKey: "account.report_invoice",
      slot: "after_body",
      availableReportKeys: ["account.report_invoice", "sale.report_saleorder"],
    });
    expect(built.ok).toBe(true);
    if (!built.ok) return;
    expect(built.op.type).toBe("report.inherit");
    expect(built.op.params.expect_matches).toBe(1);
    expect(built.op.params.xpath).toBe("//div[@class='page']");
    expect(built.op.params.position).toBe("after");
    expect(built.op.params.slot).toBe("after_body");
    expect(built.op.params.base_report_key).toBe("account.report_invoice");
  });

  it("refuses a missing base report key", () => {
    const built = buildReportInheritOp({
      baseReportKey: "missing.report_key",
      slot: DEFAULT_INHERIT_SLOT,
      availableReportKeys: ["account.report_invoice"],
    });
    expect(built.ok).toBe(false);
    if (built.ok) return;
    expect(built.error).toMatch(/does not exist/i);
  });

  it("refuses empty base key", () => {
    const built = buildReportInheritOp({
      baseReportKey: "  ",
      slot: "header",
      availableReportKeys: ["account.report_invoice"],
    });
    expect(built.ok).toBe(false);
  });

  it("refuses RT-22 root replace on / and page", () => {
    expect(
      reportInheritRootReplaceIssue({ xpath: "/", position: "replace" }),
    ).toBe(RT22_ROOT_REPLACE_MESSAGE);
    expect(
      reportInheritRootReplaceIssue({
        xpath: "//div[@class='page']",
        position: "replace",
      }),
    ).toBe(RT22_ROOT_REPLACE_MESSAGE);
    expect(
      reportInheritRootReplaceIssue({
        xpath: "//t[@t-name='sale.report_saleorder_document']",
        position: "replace",
      }),
    ).toBe(RT22_ROOT_REPLACE_MESSAGE);
    // Slot positions are never replace — always allowed.
    expect(
      reportInheritRootReplaceIssue({
        xpath: "//div[@class='page']",
        position: "after",
      }),
    ).toBeNull();
  });

  it("round-trips slot from compiled inherit arch", () => {
    const anchor = inheritAnchorForSlot("before_body");
    const arch = `<t t-name="x" t-inherit="sale.report_saleorder" t-inherit-mode="extension">
  <xpath expr="${anchor.xpath}" position="${anchor.position}">
    <p>Hi</p>
  </xpath>
</t>`;
    const parsed = parseInheritSlotFromArch(arch);
    expect(parsed.baseReportKey).toBe("sale.report_saleorder");
    expect(parsed.slot).toBe("before_body");
    expect(slotFromXpathPosition(parsed.xpath!, parsed.position!)).toBe(
      "before_body",
    );
  });
});

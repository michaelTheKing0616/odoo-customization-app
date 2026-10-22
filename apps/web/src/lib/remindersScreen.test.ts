import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  canSubmitReminder,
  emptyReminderGuide,
  intervalLabel,
  reminderCreatedGuide,
  reminderErrorGuide,
  reminderHonestyGuide,
  reminderScheduleSummary,
  resolveReminderStep,
  sanitizeReminderCopy,
} from "./remindersScreen";

describe("remindersScreen", () => {
  it("keeps Create the reminder as the primary CTA copy", () => {
    expect(PRIMARY_CTA).toBe("Create the reminder");
  });

  it("strips em and en dashes", () => {
    expect(sanitizeReminderCopy("Schedule — then create")).toBe("Schedule - then create");
    expect(sanitizeReminderCopy("a–b")).toBe("a-b");
  });

  it("resolves stages from confirm and result", () => {
    expect(
      resolveReminderStep({
        hasResult: false,
        confirmOpen: false,
        scheduleTouched: false,
        composing: true,
      }),
    ).toBe("compose");
    expect(
      resolveReminderStep({
        hasResult: false,
        confirmOpen: false,
        scheduleTouched: true,
        composing: true,
      }),
    ).toBe("schedule");
    expect(
      resolveReminderStep({
        hasResult: false,
        confirmOpen: true,
        scheduleTouched: true,
        composing: true,
      }),
    ).toBe("confirm");
    expect(
      resolveReminderStep({
        hasResult: true,
        confirmOpen: false,
        scheduleTouched: true,
        composing: false,
      }),
    ).toBe("created");
  });

  it("honesty differs for schedule on vs template-only", () => {
    const on = reminderHonestyGuide(true);
    expect(on.title.toLowerCase()).toContain("enabled");
    expect(on.why.toLowerCase()).toContain("active ir.cron");
    const off = reminderHonestyGuide(false);
    expect(off.title.toLowerCase()).toContain("template only");
    expect(off.why.toLowerCase()).toContain("no ir.cron");
  });

  it("schedule summary is honest about enable state", () => {
    const enabled = reminderScheduleSummary({
      createCron: true,
      mode: "overdue",
      intervalNumber: 1,
      intervalType: "days",
      dueSoonDays: 2,
      dateField: "x_due_date",
    });
    expect(enabled.enabled).toBe(true);
    expect(enabled.headline).toBe("Schedule enabled");
    expect(enabled.detail).toMatch(/every 1 day/i);

    const off = reminderScheduleSummary({
      createCron: false,
      mode: "due_soon",
      intervalNumber: 2,
      intervalType: "hours",
      dueSoonDays: 3,
      dateField: "x_due_date",
    });
    expect(off.enabled).toBe(false);
    expect(off.headline).toBe("Schedule off");
    expect(off.detail.toLowerCase()).toContain("no automatic sends");
  });

  it("created guide names cron when present", () => {
    const withCron = reminderCreatedGuide({ mailTemplateId: 44, cronId: 91 });
    expect(withCron.title.toLowerCase()).toContain("schedule enabled");
    expect(withCron.why).toContain("91");
    const templateOnly = reminderCreatedGuide({ mailTemplateId: 44, cronId: null });
    expect(templateOnly.title.toLowerCase()).toContain("stayed off");
  });

  it("empty guide carries what/why/next", () => {
    const g = emptyReminderGuide();
    expect(g.title).toMatch(/No reminder/i);
    expect(g.why.toLowerCase()).toContain("mail.template");
    expect(g.next.toLowerCase()).toContain("create the reminder");
  });

  it("error guide classifies model-not-found", () => {
    const g = reminderErrorGuide("create", "Model x_lib_loan not found");
    expect(g.title).toMatch(/Could not create/i);
    expect(g.why.toLowerCase()).toContain("missing");
  });

  it("interval label and submit gate", () => {
    expect(intervalLabel(1, "days")).toBe("Every 1 day");
    expect(intervalLabel(2, "hours")).toBe("Every 2 hours");
    expect(
      canSubmitReminder({
        name: "A",
        model: "x_m",
        dateField: "x_d",
        canCreate: true,
      }),
    ).toBe(true);
    expect(
      canSubmitReminder({
        name: "",
        model: "x_m",
        dateField: "x_d",
        canCreate: true,
      }),
    ).toBe(false);
    expect(
      canSubmitReminder({
        name: "A",
        model: "x_m",
        dateField: "x_d",
        canCreate: false,
      }),
    ).toBe(false);
  });
});

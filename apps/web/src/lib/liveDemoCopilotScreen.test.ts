import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  declinedLiveDemoGuide,
  emptyLiveDemoGuide,
  liveDemoErrorGuide,
  liveDemoHonestyGuide,
  liveDemoStepFromState,
  meetingCreatedGuide,
  sanitizeLiveDemoCopy,
} from "@/lib/liveDemoCopilotScreen";

describe("liveDemoCopilotScreen", () => {
  it("names Launch bot as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Launch bot");
  });

  it("steps Meeting → Consent → Launch → Live", () => {
    expect(
      liveDemoStepFromState({
        hasSession: false,
        declined: false,
        consentAccepted: false,
        botJoined: false,
        hasLiveFeed: false,
      }),
    ).toBe(1);
    expect(
      liveDemoStepFromState({
        hasSession: true,
        declined: false,
        consentAccepted: false,
        botJoined: false,
        hasLiveFeed: false,
      }),
    ).toBe(2);
    expect(
      liveDemoStepFromState({
        hasSession: true,
        declined: false,
        consentAccepted: true,
        botJoined: false,
        hasLiveFeed: false,
      }),
    ).toBe(3);
    expect(
      liveDemoStepFromState({
        hasSession: true,
        declined: false,
        consentAccepted: true,
        botJoined: true,
        hasLiveFeed: false,
      }),
    ).toBe(4);
    expect(
      liveDemoStepFromState({
        hasSession: true,
        declined: true,
        consentAccepted: false,
        botJoined: false,
        hasLiveFeed: false,
      }),
    ).toBe(2);
  });

  it("states honesty for unset, mock, and live", () => {
    const unset = liveDemoHonestyGuide(null);
    expect(unset.title.toLowerCase()).toMatch(/consent|mock|live/);
    const mock = liveDemoHonestyGuide(true);
    expect(mock.title.toLowerCase()).toContain("mock");
    expect(mock.why.toLowerCase()).toMatch(/no real|not driving|ui/);
    const live = liveDemoHonestyGuide(false);
    expect(live.title.toLowerCase()).toContain("live");
    expect(live.why.toLowerCase()).toMatch(/attendee|visible/);
    expect(sanitizeLiveDemoCopy("a — b – c")).toBe("a - b - c");
  });

  it("covers empty, meeting, and declined what/why/next", () => {
    expect(emptyLiveDemoGuide().next.toLowerCase()).toContain("create session");
    expect(meetingCreatedGuide().why.toLowerCase()).toContain("blocked");
    expect(declinedLiveDemoGuide().title.toLowerCase()).toContain("declined");
  });

  it("classifies launch and consent errors", () => {
    const launch = liveDemoErrorGuide("launch", "Attendee timeout");
    expect(launch.title.toLowerCase()).toContain("launch");
    expect(launch.next.toLowerCase()).toMatch(/refresh|diagnose/);
    const consent = liveDemoErrorGuide("consent", "Forbidden");
    expect(consent.why.toLowerCase()).toMatch(/audit|consent/);
  });
});

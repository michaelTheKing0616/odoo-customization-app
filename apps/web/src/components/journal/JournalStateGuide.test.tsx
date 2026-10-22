import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { JournalStateGuide } from "@/components/journal/JournalStateGuide";
import { journalHonestyGuide } from "@/lib/journalScreen";

afterEach(() => cleanup());

describe("JournalStateGuide", () => {
  it("renders what/why/next and strips em dashes", () => {
    render(
      <JournalStateGuide
        testId="journal-guide-sanitize"
        guide={{ title: "Title — here", why: "Why – detail", next: "Next step" }}
      />,
    );
    expect(screen.getByTestId("journal-guide-sanitize-title")).toHaveTextContent("Title - here");
    expect(screen.getByTestId("journal-guide-sanitize-why")).toHaveTextContent("Why - detail");
    expect(screen.getByTestId("journal-guide-sanitize-next")).toHaveTextContent("Next step");
  });

  it("renders honesty guide copy", () => {
    render(<JournalStateGuide testId="journal-honesty" guide={journalHonestyGuide()} />);
    expect(screen.getByTestId("journal-honesty-title")).toHaveTextContent(/partial|Audit is replay/i);
  });
});

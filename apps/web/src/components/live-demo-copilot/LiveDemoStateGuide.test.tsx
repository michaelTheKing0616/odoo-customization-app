/** @vitest-environment happy-dom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LiveDemoStateGuide } from "./LiveDemoStateGuide";

afterEach(() => cleanup());

describe("LiveDemoStateGuide", () => {
  it("renders what/why/next and strips em dashes", () => {
    render(
      <LiveDemoStateGuide
        testId="live-demo-sample"
        guide={{ title: "Title — here", why: "Why – detail", next: "Do the next thing" }}
      />,
    );
    expect(screen.getByTestId("live-demo-sample-title")).toHaveTextContent("Title - here");
    expect(screen.getByTestId("live-demo-sample-why")).toHaveTextContent("Why - detail");
    expect(screen.getByTestId("live-demo-sample-next")).toHaveTextContent("Do the next thing");
  });
});

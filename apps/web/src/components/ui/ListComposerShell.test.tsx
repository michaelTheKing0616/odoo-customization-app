/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ListComposerShell } from "./ListComposerShell";
import { ComposerSessionBar } from "./ComposerSessionBar";

afterEach(() => cleanup());

describe("ListComposerShell", () => {
  it("renders list and detail panes", () => {
    render(
      <ListComposerShell
        list={<div>List side</div>}
        detail={
          <>
            <ComposerSessionBar
              sessionState="draft"
              hint="Name the item."
              submitLabel="Create"
              onDiscard={() => undefined}
              testIdPrefix="menus"
            />
            <div>Composer body</div>
          </>
        }
      />,
    );
    expect(screen.getByTestId("list-composer-shell")).toBeTruthy();
    expect(screen.getByTestId("list-composer-list").textContent).toMatch(/List side/);
    expect(screen.getByTestId("list-composer-pane").textContent).toMatch(/Composer body/);
    expect(screen.getByTestId("menus-session-bar")).toBeTruthy();
    expect(screen.getByTestId("menus-session-state").textContent).toMatch(/Draft/);
  });
});

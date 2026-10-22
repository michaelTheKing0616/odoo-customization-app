import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn() }),
}));

import { ClarifyInterstitial } from "@/components/studio/ClarifyInterstitial";
import type {
  StudioClarification,
  StudioInstallStep,
} from "@/lib/studio-session";

afterEach(() => cleanup());

const STEP: StudioInstallStep = {
  title: "Install these apps before you build",
  message:
    "Your design uses CRM, which is not installed yet. Install now, then build.",
  apps: [
    {
      module: "crm",
      label: "CRM",
      why: "Your design builds on CRM (Lead/Opportunity).",
      models: ["crm.lead"],
      installable: true,
    },
  ],
  can_install: true,
  install_label: "Install CRM",
  blocked_message:
    "Install the apps listed above first. Your design is built on them, so App Studio can't build or apply it until they are on your database.",
};

function diagnosis(step: StudioInstallStep | null): StudioClarification {
  return {
    kind: "diagnosis",
    merge_key: "diagnosis",
    question: "We'll build: lead scoring",
    understanding: {
      title: "Lead scoring",
      host_model: "crm.lead",
      host_label: "CRM",
      inherit_existing: true,
    },
    install_step: step,
  };
}

describe("Install step on the diagnosis", () => {
  it("shows which apps and why, and keeps Generate disabled with a plain reason", () => {
    render(
      <ClarifyInterstitial
        clarification={diagnosis(STEP)}
        onAnswer={vi.fn()}
        onInstallApps={vi.fn()}
      />,
    );
    const card = screen.getByTestId("studio-install-step");
    expect(card.textContent).toContain("CRM");
    expect(card.textContent).toContain("Your design builds on CRM");
    const confirm = screen.getByTestId(
      "studio-diagnosis-confirm",
    ) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    expect(confirm.getAttribute("aria-describedby")).toBe(
      "studio-diagnosis-install-hint",
    );
    expect(
      screen.getByTestId("studio-diagnosis-install-hint").textContent,
    ).toMatch(/can't build or apply/);
  });

  it("installs on click", async () => {
    const onInstallApps = vi.fn().mockResolvedValue(undefined);
    render(
      <ClarifyInterstitial
        clarification={diagnosis(STEP)}
        onAnswer={vi.fn()}
        onInstallApps={onInstallApps}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByTestId("studio-install-step-install"));
    });
    expect(onInstallApps).toHaveBeenCalledTimes(1);
  });

  it("shows the install error in plain words", async () => {
    const onInstallApps = vi
      .fn()
      .mockRejectedValue(
        new Error(
          "CRM was not installed because this connection is read-only.",
        ),
      );
    render(
      <ClarifyInterstitial
        clarification={diagnosis(STEP)}
        onAnswer={vi.fn()}
        onInstallApps={onInstallApps}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByTestId("studio-install-step-install"));
    });
    expect(screen.getByTestId("studio-install-step-error").textContent).toMatch(
      /read-only/,
    );
  });

  it("enables Generate when nothing is left to install", () => {
    render(
      <ClarifyInterstitial
        clarification={diagnosis(null)}
        onAnswer={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("studio-install-step")).toBeNull();
    expect(
      (screen.getByTestId("studio-diagnosis-confirm") as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it("offers Check again when the database can't install from here", () => {
    render(
      <ClarifyInterstitial
        clarification={diagnosis({
          ...STEP,
          can_install: false,
          install_label: "Check again",
        })}
        onAnswer={vi.fn()}
        onInstallApps={vi.fn()}
      />,
    );
    expect(screen.getByTestId("studio-install-step-install").textContent).toBe(
      "Check again",
    );
    expect(
      (screen.getByTestId("studio-diagnosis-confirm") as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });

  it("Check again re-checks the database", async () => {
    const onInstallApps = vi.fn().mockResolvedValue(undefined);
    render(
      <ClarifyInterstitial
        clarification={diagnosis({ ...STEP, can_install: false, install_label: "Check again" })}
        onAnswer={vi.fn()}
        onInstallApps={onInstallApps}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByTestId("studio-install-step-install"));
    });
    expect(onInstallApps).toHaveBeenCalledTimes(1);
  });
  it("shows the read-only state up front and keeps Install disabled", () => {
    const onInstallApps = vi.fn();
    render(
      <ClarifyInterstitial
        clarification={diagnosis(STEP)}
        onAnswer={vi.fn()}
        onInstallApps={onInstallApps}
        connectionReadOnly
      />,
    );
    expect(screen.getByTestId("studio-install-step-readonly").textContent).toContain(
      "Switch the connection to Standard",
    );
    const install = screen.getByTestId("studio-install-step-install") as HTMLButtonElement;
    expect(install.disabled).toBe(true);
    expect(install.getAttribute("aria-describedby")).toBe("studio-install-step-readonly-help");
    fireEvent.click(install);
    expect(onInstallApps).not.toHaveBeenCalled();
  });

  it("uses the server's read-only step when the connection prop is not known", () => {
    render(
      <ClarifyInterstitial
        clarification={diagnosis({
          ...STEP,
          can_install: false,
          read_only: true,
          read_only_message: "This connection is read-only. Switch the connection to Standard in Connections.",
        })}
        onAnswer={vi.fn()}
        onInstallApps={vi.fn()}
      />,
    );
    expect(screen.getByTestId("studio-install-step-readonly")).toBeTruthy();
    expect((screen.getByTestId("studio-install-step-install") as HTMLButtonElement).disabled).toBe(true);
  });

  it("keeps Generate closed while the design refresh is pending", async () => {
    const onInstallApps = vi.fn().mockResolvedValue(undefined);
    render(
      <ClarifyInterstitial
        clarification={diagnosis({
          title: "Update the design for the installed apps",
          message: "The apps are installed. App Studio now updates your design to use their real fields before you build.",
          apps: [],
          can_install: true,
          install_label: "Update the design",
          blocked_message: "Update the design for the installed apps first, then build.",
          refresh: true,
        })}
        onAnswer={vi.fn()}
        onInstallApps={onInstallApps}
      />,
    );
    expect(screen.getByTestId("studio-install-step-install").textContent).toBe("Update the design");
    expect((screen.getByTestId("studio-diagnosis-confirm") as HTMLButtonElement).disabled).toBe(true);
    await act(async () => {
      fireEvent.click(screen.getByTestId("studio-install-step-install"));
    });
    expect(onInstallApps).toHaveBeenCalledTimes(1);
  });
});

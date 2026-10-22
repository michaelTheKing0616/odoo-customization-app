/**
 * UI-S-37 Live Demo Co-Pilot screen logic and copy.
 * Pure helpers. No React.
 * Honesty: mock mode is UI-only; live mode joins a visible Attendee bot.
 * Answers stay on the private presenter overlay. Never share that window.
 */

export const PAGE_TITLE = "Live Demo Co-Pilot";
export const PAGE_DESCRIPTION =
  "Consent-first meeting assist. A visible Attendee bot joins Zoom, Meet, or Teams. Answers stay private on your presenter overlay.";
export const PRIMARY_CTA = "Launch bot";

export const LIVE_DEMO_STEPS = ["Meeting", "Consent", "Launch", "Live"] as const;
export type LiveDemoStepLabel = (typeof LIVE_DEMO_STEPS)[number];
export type LiveDemoStepIndex = 1 | 2 | 3 | 4;

export type LiveDemoGuide = { title: string; why: string; next: string };

export type LiveDemoErrorContext =
  | "disclosure"
  | "create"
  | "consent"
  | "launch"
  | "leave"
  | "status"
  | "feed"
  | "overlay"
  | "generic";

/** Strip em / en dashes from UI copy (playbook law 9). */
export function sanitizeLiveDemoCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function liveDemoStepFromState(opts: {
  hasSession: boolean;
  declined: boolean;
  consentAccepted: boolean;
  botJoined: boolean;
  hasLiveFeed: boolean;
}): LiveDemoStepIndex {
  if (opts.declined) return 2;
  if (opts.botJoined || opts.hasLiveFeed) return 4;
  if (opts.consentAccepted) return 3;
  if (opts.hasSession) return 2;
  return 1;
}

export function liveDemoHonestyGuide(mockMode: boolean | null | undefined): LiveDemoGuide {
  if (mockMode === true) {
    return {
      title: "Mock mode. No real meeting bot.",
      why: "ATTENDEE_ALLOW_MOCK is on and Attendee is not driving a live join. Injected lines exercise Stage 1/2 and the overlay only.",
      next: "Use mock for UI checks. For a real demo, configure Attendee and turn mock off. Keep the presenter overlay off the shared screen.",
    };
  }
  if (mockMode === false) {
    return {
      title: "Live Attendee capture. Visible bot joins the meeting.",
      why: "After consent, Launch bot asks Attendee to join Zoom, Meet, or Teams as a visible participant. Stage 1/2 answers stay on your private overlay.",
      next: "Notify attendees before launch. Share the meeting or Odoo window only. Never share the presenter overlay.",
    };
  }
  return {
    title: "Consent first. Mock and live stay honest.",
    why: "Nothing joins a meeting until you record consent and notify attendees. Mock mode never joins; live mode uses a visible Attendee bot.",
    next: "Create a session, record consent, then Launch bot. Open the presenter overlay on a second display.",
  };
}

export function emptyLiveDemoGuide(): LiveDemoGuide {
  return {
    title: "No session yet",
    why: "A meeting URL and consent audit are required before any bot can join.",
    next: "Paste the Zoom, Meet, or Teams link, set your display name(s), then Create session.",
  };
}

export function meetingCreatedGuide(): LiveDemoGuide {
  return {
    title: "Session ready for consent",
    why: "The session exists in your workspace. Launch stays blocked until disclosure and attendee notice are recorded.",
    next: "Read the disclosure, check both required boxes, then Record consent. Decline stops all capture.",
  };
}

export function consentReadyGuide(): LiveDemoGuide {
  return {
    title: "Consent recorded. Ready to launch.",
    why: "Disclosure and attendee notice are on the audit trail. The bot has not joined yet.",
    next: "Open the presenter overlay on a private display, then Launch bot when the meeting is live.",
  };
}

export function declinedLiveDemoGuide(): LiveDemoGuide {
  return {
    title: "Session declined. No capture.",
    why: "Decline was recorded. No bot will join and no audio will be processed for this session.",
    next: "Create a new session if you later get clear consent from every attendee.",
  };
}

export function waitingHostGuide(hint?: string): LiveDemoGuide {
  const detail = sanitizeLiveDemoCopy(
    (hint || "The meeting host must admit the bot or grant recording.").slice(0, 400),
  );
  return {
    title: "Host action needed in the meeting",
    why: detail,
    next: "Admit the bot or grant recording in Zoom, Meet, or Teams, then Refresh status.",
  };
}

export function liveJoinedGuide(mockMode: boolean): LiveDemoGuide {
  if (mockMode) {
    return {
      title: "Mock session live",
      why: "Inject utterances to exercise Stage 1/2. Nothing is in a real meeting.",
      next: "Inject a client question, watch Live answers, and keep the overlay private.",
    };
  }
  return {
    title: "Bot is in the meeting",
    why: "Attendee is capturing the transcript. Odoo-relevant client questions feed Stage 1/2 into your private overlay.",
    next: "Watch Live answers here or on the overlay. Leave and end when the demo finishes.",
  };
}

export function emptyAnswersGuide(canLaunch: boolean, mockMode: boolean): LiveDemoGuide {
  if (mockMode) {
    return {
      title: "No triggered answers yet",
      why: "Stage 1 only surfaces Odoo-relevant client questions. Presenter names are ignored.",
      next: "Inject a mock client utterance that asks an Odoo question.",
    };
  }
  if (canLaunch) {
    return {
      title: "No triggered answers yet",
      why: "Answers appear after the bot joins and a client asks something Odoo-related.",
      next: "Launch bot, then watch this feed and the private overlay.",
    };
  }
  return {
    title: "No triggered answers yet",
    why: "Answers appear after consent, launch, and an Odoo-relevant client question.",
    next: "Finish consent and Launch bot when the meeting starts.",
  };
}

export function emptyTranscriptGuide(canLaunch: boolean, mockMode: boolean): LiveDemoGuide {
  if (mockMode) {
    return {
      title: "No transcript yet",
      why: "Mock lines appear when you inject an utterance.",
      next: "Type a client line and Inject mock line.",
    };
  }
  if (canLaunch) {
    return {
      title: "No transcript yet",
      why: "Speaker-tagged lines arrive from Attendee transcript webhooks after join.",
      next: "Launch bot, then Refresh status if the feed stays empty.",
    };
  }
  return {
    title: "No transcript yet",
    why: "Lines appear after the bot joins the meeting.",
    next: "Record consent, Launch bot, then watch this feed.",
  };
}

export function liveDemoErrorGuide(context: LiveDemoErrorContext, message: string): LiveDemoGuide {
  const detail = sanitizeLiveDemoCopy((message || "").trim().slice(0, 400));
  const base = {
    disclosure: {
      title: "Could not load the disclosure",
      why: "The consent copy comes from the API. Without it, consent cannot be recorded safely.",
      next: "Retry loading. If it keeps failing, check API health, then Diagnose with Expert.",
    },
    create: {
      title: "Could not create the session",
      why: "The meeting URL or workspace write failed before consent.",
      next: "Check the meeting link format, retry Create session, or Diagnose with Expert.",
    },
    consent: {
      title: "Could not record consent",
      why: "Consent must land on the immutable audit trail before launch.",
      next: "Confirm both required checkboxes, retry Record consent, or Diagnose with Expert.",
    },
    launch: {
      title: "Could not launch the bot",
      why: "Attendee rejected the join or consent gates still block launch.",
      next: "Refresh status, confirm Attendee keys, or Diagnose with Expert.",
    },
    leave: {
      title: "Could not leave and purge",
      why: "The leave or retention purge job did not finish cleanly.",
      next: "Retry leave/purge, Refresh status, or Diagnose with Expert.",
    },
    status: {
      title: "Could not refresh bot status",
      why: "Attendee status or the session row did not respond.",
      next: "Retry Refresh status. If the bot is stuck, Leave and end, or Diagnose with Expert.",
    },
    feed: {
      title: "Could not load the live feed",
      why: "Transcript or answer polling failed for this session.",
      next: "Retry the feed. Check the SSE connection on the overlay, or Diagnose with Expert.",
    },
    overlay: {
      title: "Presenter overlay could not open",
      why: "The pop-out needs a session id and an allowed window.",
      next: "Allow pop-ups for this origin, then Open presenter overlay again.",
    },
    generic: {
      title: "Something went wrong",
      why: detail || "The Live Demo Co-Pilot request did not complete.",
      next: "Retry the last action, or Diagnose with Expert.",
    },
  }[context];
  if (context === "generic" && detail) {
    return { ...base, why: detail };
  }
  return base;
}

export function modeBadgeLabel(mockMode: boolean | null | undefined): string {
  if (mockMode === true) return "Mock";
  if (mockMode === false) return "Live";
  return "Unset";
}

export function liveDemoSessionBadge(step: LiveDemoStepIndex): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  const labels = ["Meeting", "Consent", "Launch", "Live"] as const;
  const i = Math.max(1, Math.min(4, step)) - 1;
  const variants = ["default", "warning", "info", "success"] as const;
  return { label: labels[i], variant: variants[i] };
}

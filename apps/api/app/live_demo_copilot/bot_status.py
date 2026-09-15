"""Normalize Attendee bot states into presenter-facing ops status."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotStatusView:
    raw: str
    phase: str  # idle|joining|waiting_room|active|leaving|ended|error|declined|unknown
    label: str
    hint: str
    severity: str  # info|warning|danger|success|neutral
    needs_host_action: bool = False
    is_terminal: bool = False


_ALIASES = {
    "idle": "idle",
    "declined": "declined",
    "ready": "ready",
    "joining": "joining",
    "joined_not_recording": "joined_not_recording",
    "joined-not-recording": "joined_not_recording",
    "joined not recording": "joined_not_recording",
    "joined_recording": "joined_recording",
    "joined-recording": "joined_recording",
    "joined recording": "joined_recording",
    "joined_recording_paused": "joined_recording_paused",
    "joined-recording-paused": "joined_recording_paused",
    "leaving": "leaving",
    "post_processing": "post_processing",
    "post-processing": "post_processing",
    "post processing": "post_processing",
    "fatal_error": "fatal_error",
    "fatal-error": "fatal_error",
    "fatal error": "fatal_error",
    "waiting_room": "waiting_room",
    "waiting-room": "waiting_room",
    "waiting room": "waiting_room",
    "ended": "ended",
    "data_deleted": "data_deleted",
    "data-deleted": "data_deleted",
    "data deleted": "data_deleted",
    "scheduled": "scheduled",
    "staged": "staged",
    "joined_recording_permission_denied": "recording_permission_denied",
    "joined-recording-permission-denied": "recording_permission_denied",
    "joined recording permission denied": "recording_permission_denied",
}


def normalize_raw_state(raw: str | None) -> str:
    if not raw:
        return "idle"
    key = raw.strip().lower().replace("_", " ").replace("-", " ")
    key = " ".join(key.split())
    # rebuild hyphen/underscore forms
    compact = key.replace(" ", "_")
    if compact in _ALIASES:
        return _ALIASES[compact]
    spaced = key
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    # Attendee UI strings like "Joined - Recording"
    if "waiting" in key and "room" in key:
        return "waiting_room"
    if "fatal" in key and "error" in key:
        return "fatal_error"
    if "permission" in key and "denied" in key:
        return "recording_permission_denied"
    if "recording" in key and "pause" in key:
        return "joined_recording_paused"
    if "joined" in key and "recording" in key and "not" not in key:
        return "joined_recording"
    if "joined" in key and "not" in key:
        return "joined_not_recording"
    if "post" in key and "process" in key:
        return "post_processing"
    if key in {"leaving", "ended", "joining", "ready", "scheduled", "staged", "idle", "declined"}:
        return key
    return compact


def bot_status_view(raw: str | None) -> BotStatusView:
    norm = normalize_raw_state(raw)
    table: dict[str, BotStatusView] = {
        "idle": BotStatusView(norm, "idle", "Idle", "Session created — complete consent, then launch.", "neutral"),
        "declined": BotStatusView(
            norm, "declined", "Declined", "Consent declined — create a new session to continue.", "danger", is_terminal=True
        ),
        "ready": BotStatusView(norm, "joining", "Ready", "Bot reserved; joining shortly.", "info"),
        "scheduled": BotStatusView(norm, "joining", "Scheduled", "Bot is scheduled to join.", "info"),
        "staged": BotStatusView(norm, "joining", "Staged", "Bot resources allocated; joining soon.", "info"),
        "joining": BotStatusView(norm, "joining", "Joining", "Bot is entering the meeting…", "info"),
        "waiting_room": BotStatusView(
            norm,
            "waiting_room",
            "In waiting room",
            "Admit the bot from the meeting host controls, or it will time out.",
            "warning",
            needs_host_action=True,
        ),
        "joined_not_recording": BotStatusView(
            norm, "active", "Joined (not recording)", "Bot is in the call; recording/transcription not active yet.", "warning"
        ),
        "joined_recording": BotStatusView(
            norm, "active", "Listening", "Bot is in the meeting and streaming transcript updates.", "success"
        ),
        "joined_recording_paused": BotStatusView(
            norm, "active", "Recording paused", "Bot is present but recording is paused.", "warning"
        ),
        "recording_permission_denied": BotStatusView(
            norm,
            "error",
            "Recording permission denied",
            "Grant the bot recording permission in the meeting, then refresh status.",
            "danger",
            needs_host_action=True,
        ),
        "leaving": BotStatusView(norm, "leaving", "Leaving", "Bot is leaving the meeting…", "info"),
        "post_processing": BotStatusView(
            norm, "leaving", "Post-processing", "Meeting ended; Attendee is finishing uploads.", "info"
        ),
        "ended": BotStatusView(norm, "ended", "Ended", "Session ended.", "neutral", is_terminal=True),
        "data_deleted": BotStatusView(
            norm, "ended", "Data deleted", "Attendee media/transcript data purged.", "success", is_terminal=True
        ),
        "fatal_error": BotStatusView(
            norm,
            "error",
            "Join failed",
            "Attendee reported a fatal error — check Zoom SDK credentials, meeting URL, and Attendee logs.",
            "danger",
            is_terminal=True,
        ),
    }
    if norm in table:
        return table[norm]
    return BotStatusView(
        raw=norm,
        phase="unknown",
        label=raw or "Unknown",
        hint="Unrecognized bot state — refresh status or check Attendee.",
        severity="warning",
    )

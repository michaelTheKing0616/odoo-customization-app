# Track 6 — auth and the command center

D6 and D9 are closed. D6 is self-hosted Authlib + TOTP, with Google, GitHub, and Microsoft OAuth already wired. D9 is a connection grant. This track finishes the inbox, the audit hookup, and the command center. It does not replace the login stack.

## Roles

| Role | Scope |
|---|---|
| Owner / Admin | Workspace |
| Consultant | One or more named clients |
| Client Approver | One connection grant. Sees that client's approval cards. Approves and refuses. Nothing else |
| Client Viewer | Same scope, no approve |

A client never approves their own high-risk request when they are also the requester (R3 approver ≠ requester).

## Sign-in gates

| ID | Gate |
|---|---|
| 6-1 | Google, Microsoft, and email plus mandatory TOTP all complete with zero manual account-linking steps (master DoD 29). GitHub stays as an extra provider already built; it is not a substitute for the Microsoft path |
| 6-2 | Client Approver for client A receives 404 on client B and cannot call consultant routes. Already tested in `test_client_approver_isolation.py`. Extend the same policy to the new inbox |
| 6-3 | Every login, logout, grant, revoke, TOTP enrol, and permission change appends to the Track 5 hash chain. No second auth log (master DoD 31) |
| 6-4 | Order 14b: one screen shows live data from Tracks 1–5 at once in one environment (master DoD 32) |

SAML is later. Do not block 6-1 on it.

## Information architecture

Consultant command center:

- Home: clients, pending approvals, failed jobs, drift.
- Per client: connection, open change-sets, last snapshot, bot roster when T8 exists.
- Team: grants and roles.
- Billing: existing `/settings/billing`. Do not invent a second billing model.
- Settings: API keys, OAuth identities, audit verify.

Client Approver home is the approval inbox filtered to their grant. It is not the consultant home with buttons hidden.

## Approval inbox (new)

Reads `02_APPROVAL_FLOW.md`. The page renders the plan card from the change-set. Approve posts the fingerprint. A mismatched fingerprint is rejected. Expiry is shown. R3 shows both approver slots and blocks the requester.

Slack, Teams, and chatter cards, when those channels exist, contain a link. They do not contain an approve action for R≥2.

## What is already built (do not rebuild)

`users`, `workspaces`, `workspace_memberships`, `user_sessions`, `connection_access_grants`, `oauth_identities`, `totp` routes, `login_workspace`, Microsoft provider settings, `OAuthProviderButtons`.

## What is not built

Plan card UI, hash binding, two-person R3, auth rows in the hash chain, command center live five-track view.

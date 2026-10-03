# Secrets, KMS, BYO keys

**Status:** accepted (2026-10-03) for the envelope. The KMS vendor stays unchosen.

**Context:** Provider keys and connection secrets need encryption at rest. A KMS vendor is not selected.

**Options considered:**
- Pick a KMS vendor now. That would lock a vendor before one is chosen.
- Envelope encryption with the existing `fernet_key` until a vendor is chosen.

**Decision:** Fernet with the existing `fernet_key`. BYO provider keys stay under that envelope. Display the last 4 characters only. Prefer API keys over passwords. No secrets in prompts. The sandbox helper that generates an API key stays on sandboxes and is never an agent tool.

**Consequences:** A KMS migration stays a later ADR once a vendor is named. Shipping a cloud KMS client now stays out of scope.

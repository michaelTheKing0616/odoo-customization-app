# Secrets, KMS, BYO keys

**Status:** proposed

**Context:** This ADR is tracked as part of the next-phase bot engine plan in [T8_BOT_ENGINE.md](../plans/next-phase/T8_BOT_ENGINE.md).

**Decision:** Fernet until a KMS is chosen.

**Consequences:** Secret handling stays on Fernet encryption until a KMS option is decided and migrated.

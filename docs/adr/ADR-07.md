# Staging and clone provider

**Status:** open. Blocking question: who provides neutralized database clones.

**Context:** Production R3 and database-structure changes must run first on a neutralized staging copy, not on the live customer database. OQ-STAGING is still open: who provides those clones. Until a provider is chosen, the assumption is that no staging means review-only above R1.

**Options considered:**
- Operator-owned host clone. The operator provisions and maintains a neutralized copy on infrastructure they already control, then points Ingenium at that host.
- Managed clone service. A third party provisions, refreshes, and isolates neutralized clones, and Ingenium talks to that service rather than to an operator-owned host.

**Decision:** None yet. This ADR does not pick a provider or a category.

**Consequences:** Production R3 stays blocked. Above R1 the path is review-only until staging exists. Implementing a clone client now would guess the provider.

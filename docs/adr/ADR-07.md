# Staging and clone provider

**Status:** accepted (2026-10-03). The operator provides neutralized clones. Production R3 stays blocked until a clone exists for that tenant.

**Context:** Production R3 and database-structure changes must run first on a neutralized staging copy, on a host the operator already controls. OQ-STAGING asked who provides those clones.

**Options considered:**
- Operator-owned host clone. The operator provisions and maintains a neutralized copy on infrastructure they already control, then points Ingenium at that host.
- Managed clone service. A third party provisions, refreshes, and isolates neutralized clones, and Ingenium talks to that service.

**Decision:** The operator provides the clone on a host they control. Docker sandboxes already in this repo are that host for local work. No managed clone vendor. A customer production database is never cloned. Production R3 stays blocked until a neutralized clone exists for the tenant. Above R1 the path stays review-only until that clone exists.

**Consequences:** Building a client for a managed clone vendor stays out of scope. A production R3 apply stays refused while the tenant has no operator-owned neutralized clone. Review-only above R1 continues until that clone exists.

**How to revisit:** A paying tenant needs a managed clone vendor, named and budgeted, in a new ADR.

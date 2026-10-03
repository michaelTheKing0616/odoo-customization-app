# Supported Odoo versions

**Status:** accepted (D11, confirmed 2026-10-03). The version matrix is unchanged.

**Context:** This ADR records the D11 version matrix so compatibility, sandbox, and gates cannot invent a different set of supported majors. It is tracked in [T8_BOT_ENGINE.md](../plans/next-phase/T8_BOT_ENGINE.md).

**Decision:** Community 20, 19, 18, and 17 are GA. 16 is experimental. Majors at or below 15 are refused. The local Odoo 20 stack is specified in `docker/docker-compose.odoo20.yml` and publishes host Odoo at http://127.0.0.1:8073. `docker/run-odoo20-smoke.sh` prints the compose command and does not start containers. Live Odoo 20 version-table probes stay skipped until `ODOO20_URL` is set.

**Consequences:** A major at or below 15 stays refused. Calling `docker/docker-compose.odoo20.yml` missing is a false statement. A live Odoo 20 version-table probe stays skipped until `ODOO20_URL` is set.

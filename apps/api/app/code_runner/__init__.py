"""Code runner v2 (BRIDGE_RUNNER_SPEC items 1-7): Odoo-aware editor services.

Scripts use the existing runner's globals: ``odoo.execute_kw(model, method, args, kwargs)``,
``log``, ``progress``. This package only reads the live database's public ORM metadata;
it never writes to Odoo.
"""

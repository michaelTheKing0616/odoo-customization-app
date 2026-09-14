"""Domain-agnostic Autopilot connectors (payments → inbound → messaging → hardware → payroll)."""

from app.job_autopilot.connectors.catalog import infer_connector_ids
from app.job_autopilot.connectors.runner import run_connectors

__all__ = ["infer_connector_ids", "run_connectors"]

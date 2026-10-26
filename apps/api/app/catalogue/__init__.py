"""Ingenium task catalogue (TAX-CATALOGUE-IMPORT): Odoo 17-20 Community tasks as checked-in data."""

from app.catalogue.loader import CatalogueError, Task, by_id, load, tasks_for_version

__all__ = ["CatalogueError", "Task", "by_id", "load", "tasks_for_version"]

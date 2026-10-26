"""Operator tool: python -m app.catalogue --import <catalogue.csv>."""

import sys
from pathlib import Path

from app.catalogue.loader import import_csv

if len(sys.argv) != 3 or sys.argv[1] != "--import":
    sys.exit("usage: python -m app.catalogue --import <catalogue.csv>")
c = import_csv(Path(sys.argv[2]))
print(f"imported {len(c.tasks)} tasks sha256={c.sha256}")

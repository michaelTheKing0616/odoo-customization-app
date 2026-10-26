"""Generated Odoo module inventory for the Business fit-gap concept table.

Source of truth is the repo, not memory: module install tasks in the catalogue
(``mod:<name>:install`` rows, versions 17-20) plus the Community module lists
(``app/data/community_modules_<v>_0.json``, 17-19; 20 follows 19). A module in the catalogue
and in a Community list is ``community``. Enterprise modules are not visible in these files;
they come from the reviewed overlay (``fitgap_table.json`` -> ``enterprise_modules``) and must
never appear in a Community list (drift test).

Regenerate: ``python -m app.bots.fitgap.inventory`` (writes ``inventory.gen.json``).
"""

from __future__ import annotations

import csv
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

API = Path(__file__).resolve().parents[3]
CATALOGUE = API / "app" / "catalogue" / "data" / "catalogue.csv"
COMMUNITY = API / "app" / "data" / "community_modules_{v}_0.json"
GEN_PATH = Path(__file__).with_name("inventory.gen.json")
MAJORS = (17, 18, 19, 20)


def community_lists() -> dict[int, frozenset[str]]:
    out = {
        v: frozenset(json.loads(Path(str(COMMUNITY).format(v=v)).read_text())["modules"])
        for v in (17, 18, 19)
    }
    out[20] = out[19]
    return out


def build() -> dict[str, Any]:
    com = community_lists()
    mods: dict[str, Any] = {}
    with CATALOGUE.open(newline="") as fh:
        for r in csv.DictReader(fh):
            rid = r["id"]
            if not (rid.startswith("mod:") and rid.endswith(":install")):
                continue
            name = rid.split(":")[1]
            vs = sorted(int(v) for v in r["versions"].split("|") if v.strip().isdigit())
            mods[name] = {
                "versions": [v for v in vs if v in MAJORS],
                "edition": "community" if any(name in com[v] for v in vs) else "unlisted",
            }
    return {
        "generated_from": {
            "catalogue_sha256": hashlib.sha256(CATALOGUE.read_bytes()).hexdigest(),
            "community_lists": [f"community_modules_{v}_0.json" for v in (17, 18, 19)],
        },
        "modules": dict(sorted(mods.items())),
    }


def render(inv: dict[str, Any]) -> str:
    return json.dumps(inv, indent=1, sort_keys=True) + "\n"


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    return json.loads(GEN_PATH.read_text())["modules"]


if __name__ == "__main__":  # pragma: no cover - maintenance entry point
    GEN_PATH.write_text(render(build()))

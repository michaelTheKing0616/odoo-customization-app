"""Verify every debug-notes needle against the odoo:<v> image sources (read-only).

Usage (from apps/api): PYTHONPATH=. python evals/bots/verify_debug_notes.py
Writes evals/bots/debug_notes_evidence.json: {signature: {version: {file, line, ok}}}.
Containers run with --network none and a read-only rootfs; nothing is executed from Odoo.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.bots.debug_notes import CATALOGUE, VERSIONS

OUT = Path(__file__).with_name("debug_notes_evidence.json")
PROBE = """
import importlib.util, json, os, sys
spec = importlib.util.find_spec("odoo")  # locate only; never import Odoo
root = os.path.dirname(list(spec.submodule_search_locations)[0])
out = {}
for sid, needle, rel in json.load(sys.stdin):
    p = os.path.join(root, rel)
    line = 0
    if os.path.isfile(p):
        for i, ln in enumerate(open(p, encoding="utf-8", errors="ignore"), 1):
            if needle in ln:
                line = i
                break
    out[sid] = {"file": rel, "line": line, "ok": bool(line)}
print(json.dumps(out))
"""


def main() -> int:
    ev: dict[str, dict[int, dict]] = {s.id: {} for s in CATALOGUE}
    for v in VERSIONS:
        job = [[s.id, s.needles[v], s.files[v]] for s in CATALOGUE if v in s.needles]
        res = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "--network",
                "none",
                "--read-only",
                "--entrypoint",
                "python3",
                f"odoo:{v}",
                "-c",
                PROBE,
            ],
            input=json.dumps(job),
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
        for sid, r in json.loads(res.stdout.strip().splitlines()[-1]).items():
            ev[sid][v] = r
    OUT.write_text(json.dumps(ev, indent=1, sort_keys=True) + "\n")
    bad = [(s, v) for s, m in ev.items() for v, r in m.items() if not r["ok"]]
    print(f"{len(ev)} signatures, {sum(map(len, ev.values()))} checks, {len(bad)} failed")
    for b in bad:
        print("FAILED", *b)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run orchestration: dry run by default, receipt → approval → real run → undo; pause/stop/resume.

AI never decides here. Every gate is code: receipt matches the exact code and connection, is fresh,
money and high-risk runs need an approver, and the connection's own write mode is respected.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.code_runner.child import EV_PREFIX

RECEIPT_TTL_S = 30 * 60
RUN_TIMEOUT_S = 15 * 60
MAX_EVENTS = 20000
MONEY_MODELS = re.compile(r"^(account\.|sale\.order|purchase\.order|pos\.|hr\.payslip|hr\.expense|stock\.valuation|payment\.)")
_lock = threading.RLock()
_runs: dict[str, dict[str, Any]] = {}
_procs: dict[str, subprocess.Popen[str]] = {}


def _dir() -> Path:
    d = Path(os.environ.get("INGENIUM_CODE_RUNNER_DIR") or Path.home() / ".ingenium" / "code_runner")
    d.mkdir(parents=True, exist_ok=True)
    return d


def code_hash(code: str, params: dict[str, Any] | None = None) -> str:
    """The receipt binds the exact code and parameter values (a dry run with other values isn't proof)."""
    raw = (code or "") + ("\0" + json.dumps(params, sort_keys=True, default=str) if params else "")
    return hashlib.sha256(raw.encode()).hexdigest()


def _save(run: dict[str, Any]) -> None:
    path = _dir() / f"{run['id']}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(run, default=str))
    tmp.replace(path)


def get(run_id: str) -> dict[str, Any] | None:
    with _lock:
        if run_id in _runs:
            return _runs[run_id]
    path = _dir() / f"{re.sub(r'[^a-f0-9-]', '', run_id)}.json"
    if path.exists():
        run = json.loads(path.read_text())
        with _lock:
            _runs[run_id] = run
        return run
    return None


def list_runs(connection_id: str, limit: int = 50) -> list[dict[str, Any]]:
    out = []
    for p in sorted(_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:500]:
        try:
            r = get(p.stem)
        except (OSError, ValueError):
            continue
        if r and r.get("connection_id") == connection_id:
            out.append(summary(r))
        if len(out) >= limit:
            break
    return out


def summary(r: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "mode", "status", "params", "script_id", "undone_by", "created_at", "ended_at", "code_hash", "safety", "estimate", "approval",
            "receipt_of", "undo_of", "resume_of", "progress", "counts", "error", "requested_by", "name")
    return {k: r.get(k) for k in keys}


# ---------------------------------------------------------------- safety meter + money guard
def safety(changes: list[dict[str, Any]], calls: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    score = 0
    writes = [c for c in changes if c["op"] in {"create", "write"}]
    unlinks = [c for c in changes if c["op"] == "unlink"]
    methods = [c for c in changes if c["op"] == "method"]
    money = sorted({c["model"] for c in changes if MONEY_MODELS.search(c["model"])})
    if len(writes) > 1000:
        score += 3; reasons.append(f"{len(writes)} records change.")
    elif len(writes) > 100:
        score += 2; reasons.append(f"{len(writes)} records change.")
    if unlinks:
        score += 3; reasons.append(f"{len(unlinks)} record(s) are deleted; deletes can't be undone (archive instead).")
    if methods:
        score += 2; reasons.append(f"{len(methods)} button/action call(s); their side effects can't be undone automatically.")
    if money:
        score += 3; reasons.append("Touches money records: " + ", ".join(money) + ".")
    models = {c["model"] for c in changes}
    if len(models) > 3:
        score += 1; reasons.append(f"Changes {len(models)} kinds of record.")
    level = "none" if not changes else "low" if score <= 1 else "medium" if score <= 4 else "high"
    return {"level": level, "score": score, "reasons": reasons or (["Reads only."] if not changes else ["Small, undoable change."]),
            "money": money, "needs_approval": level == "high" or bool(money), "undoable": not unlinks and not methods,
            "calls": len(calls)}


def estimate(run: dict[str, Any]) -> dict[str, Any] | None:
    counts = run.get("sample_counts") or []
    ms = float(run.get("timing_ms") or 0)
    seen = max(1, sum(1 for c in run.get("calls", []) if c["method"] in {"search", "search_read"}))
    if not counts:
        return None
    full = max(c["count"] for c in counts)
    sample = min(20, full) or 1
    factor = full / sample
    return {"records": full, "sampled": sample, "seconds": round(ms / 1000 * factor, 1),
            "writes": round(len(run.get("changes", [])) * factor), "basis": f"{sample} of {full} records, {seen} search(es)"}


# ---------------------------------------------------------------- profile with fixes
def profile(calls: list[dict[str, Any]], code: str) -> dict[str, Any]:
    per: dict[int, dict[str, Any]] = defaultdict(lambda: {"calls": 0, "ms": 0.0, "methods": set()})
    for c in calls:
        p = per[c.get("line") or 0]
        p["calls"] += 1; p["ms"] += c.get("ms") or 0; p["methods"].add(f"{c['model']}.{c['method']}")
    lines = (code or "").splitlines()
    rows, fixes = [], []
    for line, p in sorted(per.items(), key=lambda kv: -kv[1]["ms"]):
        src = lines[line - 1].strip() if 0 < line <= len(lines) else ""
        rows.append({"line": line, "calls": p["calls"], "ms": round(p["ms"], 1), "methods": sorted(p["methods"]), "source": src[:200]})
        meths = {m.split(".")[-1] for m in p["methods"]}
        if p["calls"] >= 20 and meths & {"write", "unlink"}:
            fixes.append({"line": line, "fix": f"{p['calls']} separate updates here. Collect the ids and call write/unlink once with the list when the values are the same."})
        elif p["calls"] >= 20 and meths & {"read", "search_read", "search"}:
            fixes.append({"line": line, "fix": f"{p['calls']} reads inside a loop. Read all records once with search_read before the loop."})
        elif p["calls"] >= 20 and "create" in meths:
            fixes.append({"line": line, "fix": f"{p['calls']} single creates. Pass a list of values to one create call."})
        if "read" in meths and re.search(r"\"read\"\s*,\s*\[\s*[^\],]+\s*\]\s*\)", src):
            fixes.append({"line": line, "fix": "read without a field list loads every field. Name the fields you need."})
    return {"lines": rows[:50], "fixes": fixes, "total_ms": round(sum(c.get("ms") or 0 for c in calls), 1), "calls": len(calls)}


# ---------------------------------------------------------------- execution
def _apply_event(run: dict[str, Any], ev: dict[str, Any]) -> None:
    t = ev.get("t")
    with _lock:
        if len(run["events"]) < MAX_EVENTS and t in {"log", "error", "progress"}:
            run["events"].append(ev)
        if t == "call":
            run["calls"].append(ev)
        elif t == "change":
            run["changes"].append(ev)
        elif t == "progress":
            run["progress"] = {"done": ev["done"], "total": ev["total"]}
        elif t == "result":
            run["results"].extend(ev.get("rows") or [])
        elif t == "error":
            run["error"] = {k: ev.get(k) for k in ("line", "message", "hint", "kind")}
        elif t == "timing":
            run["timing_ms"] = ev.get("ms")
        elif t == "sample_counts":
            run["sample_counts"] = ev.get("counts")


def _execute(run: dict[str, Any], conn: dict[str, Any], script: str, extra: dict[str, Any]) -> None:
    hidden = sorted((v for v in (extra.get("secrets") or {}).values() if len(v) >= 3), key=len, reverse=True)
    control = _dir() / f"{run['id']}.control"
    control.write_text("run")
    with tempfile.TemporaryDirectory(prefix="cr-") as td:
        cfg_path = Path(td) / "cfg.json"
        cfg_path.write_text(json.dumps({"connection": conn, "mode": run["mode"], "script": script,
                                        "control": str(control), **extra}))
        os.chmod(cfg_path, 0o600)
        api_root = Path(__file__).resolve().parents[2]
        odoo_src = api_root.parents[1] / "packages" / "odoo-client" / "src"
        env = {k: v for k, v in os.environ.items() if not re.search(r"(?i)secret|password|token|key", k)}
        env.update(CR_CONFIG=str(cfg_path), PYTHONPATH=os.pathsep.join([str(api_root), str(odoo_src)]))
        proc = subprocess.Popen([sys.executable, "-m", "app.code_runner.child"], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env)
        with _lock:
            _procs[run["id"]] = proc
            run["status"] = "running"
        deadline = time.monotonic() + RUN_TIMEOUT_S
        assert proc.stdout is not None
        for raw in proc.stdout:
            for sv in hidden:
                raw = raw.replace(json.dumps(sv)[1:-1], "***")
            if raw.startswith(EV_PREFIX):
                try:
                    _apply_event(run, json.loads(raw[len(EV_PREFIX):]))
                except ValueError:
                    pass
            if time.monotonic() > deadline:
                proc.kill()
                run["error"] = {"line": 0, "message": f"Stopped after {RUN_TIMEOUT_S // 60} minutes.", "hint": "", "kind": "Timeout"}
                break
        proc.wait()
        stderr = (proc.stderr.read() if proc.stderr else "")[-2000:]
    with _lock:
        _procs.pop(run["id"], None)
        state = control.read_text().strip() if control.exists() else "run"
        control.unlink(missing_ok=True)
        if proc.returncode != 0 and not run.get("error"):
            for sv in hidden:
                stderr = stderr.replace(sv, "***")
            run["error"] = {"line": 0, "message": _scrub(stderr) or "The script stopped unexpectedly.", "hint": "", "kind": "Crash"}
        run["status"] = "stopped" if state == "stop" else "failed" if run.get("error") else "done"
        run["ended_at"] = time.time()
        run["counts"] = _counts(run["changes"])
        run["safety"] = safety(run["changes"], run["calls"])
        run["profile"] = profile(run["calls"], script)
        if run["mode"] == "dry":
            run["estimate"] = estimate(run)
            run["receipt"] = {"code_hash": run["code_hash"], "expires_at": time.time() + RECEIPT_TTL_S} if run["status"] == "done" else None
        _save(run)


def _scrub(text: str) -> str:
    return re.sub(r"(?i)(password|secret|token|api[_-]?key)\S*\s*[:=]\s*\S+", r"\1=***", text or "").strip()[:1500]


def _counts(changes: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for c in changes:
        out[c["op"]] += 1
    return dict(out)


def start(connection_id: str, conn: dict[str, Any], script: str, *, mode: str, user: str | None = None,
          name: str = "", sample: bool = False, receipt_of: str | None = None, resume_of: str | None = None,
          undo_of: str | None = None, params: dict[str, Any] | None = None, wait: bool = False,
          secrets: dict[str, str] | None = None, script_id: str | None = None) -> dict[str, Any]:
    run = {"id": str(uuid.uuid4()), "connection_id": connection_id, "mode": mode, "status": "queued", "name": name[:120],
           "created_at": time.time(), "ended_at": None, "code_hash": code_hash(script, params), "code": script,
           "params": params or {}, "script_id": script_id,
           "requested_by": user, "receipt_of": receipt_of, "resume_of": resume_of, "undo_of": undo_of,
           "events": [], "calls": [], "changes": [], "results": [], "progress": None, "error": None, "approval": None,
           "sample": sample}
    extra: dict[str, Any] = {"sample": sample, "params": params or {}, "secrets": secrets or {}}
    if resume_of:
        prev = get(resume_of) or {}
        extra["resume_from"] = (prev.get("progress") or {}).get("done", 0)
        done: dict[str, list[int]] = defaultdict(list)
        for c in prev.get("changes", []):
            if isinstance(c.get("id"), int) and c["id"] > 0:
                done[c["model"]].append(c["id"])
        extra["done_ids"] = dict(done)
    with _lock:
        _runs[run["id"]] = run
    _save(run)
    t = threading.Thread(target=_execute, args=(run, conn, script, extra), daemon=True, name=f"cr-{run['id'][:8]}")
    t.start()
    if wait:
        t.join(RUN_TIMEOUT_S + 30)
    return run


def control(run_id: str, action: str) -> str:
    path = _dir() / f"{run_id}.control"
    if not path.exists():
        return "not_running"
    state = {"pause": "pause", "resume": "run", "stop": "stop"}[action]
    path.write_text(state)
    with _lock:
        r = _runs.get(run_id)
        if r and r["status"] in {"running", "paused"}:
            r["status"] = {"pause": "paused", "run": "running", "stop": "stopping"}[state]
    return state


# ---------------------------------------------------------------- gates
class Refused(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def check_real_run(receipt: dict[str, Any] | None, *, connection_id: str, script: str, write_mode: str,
                   params: dict[str, Any] | None = None) -> None:
    if write_mode == "observer":
        raise Refused("observer_connection", "This connection is read-only, so scripts can only dry run here.")
    if not receipt or receipt.get("mode") != "dry" or receipt.get("connection_id") != connection_id:
        raise Refused("dry_run_receipt_required", "Do a dry run of this exact script on this connection first.")
    if receipt.get("status") != "done" or not receipt.get("receipt"):
        raise Refused("dry_run_failed", "The dry run didn't finish cleanly. Fix it and dry run again.")
    if receipt["receipt"]["code_hash"] != code_hash(script, params):
        raise Refused("code_changed", "The script or its values changed since the dry run. Dry run it again.")
    if time.time() > float(receipt["receipt"]["expires_at"]):
        raise Refused("receipt_expired", "The dry run is older than 30 minutes. Dry run it again.")
    if receipt.get("sample"):
        raise Refused("sample_only", "That was a sample dry run for an estimate. Do a full dry run before the real run.")
    s = receipt.get("safety") or {}
    if s.get("needs_approval") and not (receipt.get("approval") or {}).get("approved"):
        raise Refused("approval_required", "This run touches money records or is high risk, so it needs an approver first.")


def approve(receipt: dict[str, Any], *, approver: str | None, role: str | None, auth_on: bool, requester_ok: bool) -> dict[str, Any]:
    if auth_on and role not in {"owner", "admin", "superadmin"}:
        raise Refused("approver_role_required", "Only an owner or admin can approve this run.")
    if auth_on and not requester_ok and approver and approver == receipt.get("requested_by"):
        raise Refused("self_approval", "Someone other than the person who wrote the run must approve it.")
    receipt["approval"] = {"approved": True, "by": approver, "at": time.time()}
    _save(receipt)
    return receipt["approval"]


def undo_script(run: dict[str, Any]) -> str:
    """Code (not AI) that reverses a finished real run, newest change first. Deletes and buttons are listed, not undone."""
    lines = [f"# Undo of run {run['id'][:8]}, newest change first"]
    for c in reversed(run.get("changes", [])):
        if c["op"] == "create" and isinstance(c.get("id"), int) and c["id"] > 0:
            lines.append(f"odoo.execute_kw({c['model']!r}, 'unlink', [[{c['id']}]])")
        elif c["op"] == "write" and c.get("before") is not None and c["id"] > 0:
            before = {k: (v[0] if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int) else v) for k, v in c["before"].items()}
            lines.append(f"odoo.execute_kw({c['model']!r}, 'write', [[{c['id']}], {before!r}])")
        elif c["op"] in {"unlink", "method"}:
            lines.append(f"log('Not undone: {c['op']} on {c['model']} {c.get('id') or c.get('ids')}')")
    return "\n".join(lines) + "\n"

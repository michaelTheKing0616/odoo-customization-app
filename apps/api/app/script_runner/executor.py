"""DEV-3 — subprocess execution with OS limits and cancel registry."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

_script_subprocesses: dict[str, subprocess.Popen[Any]] = {}
_lock = threading.Lock()

DEFAULT_TIMEOUT_S = 120
MEMORY_LIMIT_BYTES = 256 * 1024 * 1024


def cancel_script_if_running(job_id: str) -> None:
    with _lock:
        proc = _script_subprocesses.pop(job_id, None)
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_script_in_subprocess(
    *,
    script: str,
    connection_config: dict[str, Any],
    job_id: str,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    count_writes: bool = True,
) -> dict[str, Any]:
    """Run user script in isolated child process; return structured result."""
    with tempfile.TemporaryDirectory(prefix="oc-script-") as td:
        td_path = Path(td)
        script_path = td_path / "user_script.py"
        config_path = td_path / "config.json"
        script_path.write_text(script, encoding="utf-8")
        config_path.write_text(
            json.dumps(
                {
                    "connection": connection_config,
                    "count_writes": count_writes,
                }
            ),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["SCRIPT_RUNNER_CONFIG"] = str(config_path)
        env["SCRIPT_RUNNER_SCRIPT"] = str(script_path)
        repo_root = Path(__file__).resolve().parents[4]
        api_root = Path(__file__).resolve().parents[2]
        odoo_src = repo_root / "packages" / "odoo-client" / "src"
        env["PYTHONPATH"] = os.pathsep.join(
            str(p)
            for p in [str(api_root), str(odoo_src), env.get("PYTHONPATH", "")]
            if p
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "app.script_runner.child_main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=_posix_limits if os.name == "posix" else None,
        )
        with _lock:
            _script_subprocesses[job_id] = proc
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            return {
                "ok": False,
                "exit_code": -9,
                "stdout": stdout or "",
                "stderr": stderr or "",
                "error": f"Script exceeded {timeout_s}s timeout",
                "write_counts": {},
            }
        finally:
            with _lock:
                _script_subprocesses.pop(job_id, None)

        result: dict[str, Any] = {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "write_counts": {},
        }
        for line in reversed((stdout or "").splitlines()):
            line = line.strip()
            if line.startswith("{") and '"write_counts"' in line:
                try:
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        result["write_counts"] = payload.get("write_counts") or {}
                        result["log_lines"] = payload.get("log_lines") or []
                        break
                except json.JSONDecodeError:
                    continue
        if proc.returncode != 0 and not result.get("error"):
            result["error"] = (stderr or stdout or "Script failed")[:2000]
        return result


def _posix_limits() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (DEFAULT_TIMEOUT_S + 10, DEFAULT_TIMEOUT_S + 10))
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    except Exception:  # noqa: BLE001
        pass
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

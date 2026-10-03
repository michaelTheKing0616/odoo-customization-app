"""Phase 6 — ephemeral Docker Odoo sandbox that installs a generated module zip.

Matching-major: image is ``odoo:{16|17|18|19}`` from the connection (or explicit
``odoo_major``). Serialized via a process lock — one sandbox at a time.
Host port **18069** (avoids clash with permanent Odoo 18 on 8070).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import time
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from app.zip_safety import safe_extract, validate_zip_bytes

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
SANDBOX_COMPOSE = REPO_ROOT / "docker" / "docker-compose.sandbox.yml"
SANDBOX_ADDONS = REPO_ROOT / "docker" / "sandbox-addons"
SANDBOX_URL = "http://127.0.0.1:18069"
SANDBOX_DB = "sandbox_test"
SANDBOX_USER = "admin"
SANDBOX_PASSWORD = "admin"
ODOO_CONTAINER = "odoo-custom-sandbox-odoo"
DB_CONTAINER = "odoo-custom-sandbox-db"

SUPPORTED_SANDBOX_MAJORS = frozenset({16, 17, 18, 19})

# Serialize sandbox runs — shared addons dir + fixed compose project name.
_sandbox_lock = threading.Lock()
_active_sandbox_job_id: str | None = None
_sandbox_subprocesses: dict[str, subprocess.Popen[str]] = {}


def cancel_sandbox_if_running(job_id: str) -> None:
    """Tear down ephemeral sandbox when a background job is cancelled."""
    global _active_sandbox_job_id
    proc = _sandbox_subprocesses.pop(job_id, None)
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    if _active_sandbox_job_id != job_id:
        return
    try:
        _compose("down", "--remove-orphans", check=False)
    except Exception:  # noqa: BLE001
        logger.warning("sandbox cancel teardown failed", exc_info=True)
    finally:
        _active_sandbox_job_id = None


@dataclass
class SandboxResult:
    ok: bool
    module: str
    message: str
    log_tail: str = ""
    sandbox_url: str | None = None
    odoo_major: int | None = None
    test_failures: list[str] = field(default_factory=list)
    tests_ran: bool = False


_TEST_FAIL_LINE_RE = re.compile(r"^(FAIL|ERROR):\s*(.+)$", re.IGNORECASE)
_TEST_SUMMARY_FAIL_RE = re.compile(
    r"(?i)(\d+)\s+failed(?:\s*,\s*(\d+)\s+error)?|"
    r"FAILED\s*\(failures?=(\d+)(?:,\s*errors?=(\d+))?\)"
)
_CREDENTIAL_KV_RE = re.compile(
    r"(?i)\b(password|passwd|api_key|api-key|secret|token)\s*([=:])\s*\S+"
)


def _redact_credential_kv(match: re.Match[str]) -> str:
    return f"{match.group(1)}{match.group(2)}[redacted]"


def redact_sandbox_secrets(text: str) -> str:
    """Strip sandbox passwords / API keys before persisting Odoo fault text."""
    from app.llm_gateway.scrub import scrub

    secrets = [SANDBOX_PASSWORD]
    try:
        from app.settings import settings

        key = (settings.app_api_key or "").strip()
        if key:
            secrets.append(key)
    except Exception:  # noqa: BLE001
        pass
    scrubbed = scrub(text or "", secrets)
    return _CREDENTIAL_KV_RE.sub(_redact_credential_kv, scrubbed)


def _join_sandbox_logs(logs: list[str]) -> str:
    """Full install/test log for persistence (redacted, not tail-truncated)."""
    return redact_sandbox_secrets("\n".join(logs))


def verbatim_sandbox_error_text(*, message: str = "", log_tail: str = "") -> str:
    """Combine sandbox message + log without dropping traceback lines (T1-D3)."""
    msg = (message or "").strip()
    tail = (log_tail or "").strip()
    if msg and tail:
        if tail in msg:
            combined = msg
        elif msg in tail:
            combined = tail
        else:
            combined = f"{msg}\n{tail}"
    else:
        combined = msg or tail
    return redact_sandbox_secrets(combined)


def sandbox_job_error_from_result(result: dict[str, Any]) -> str | None:
    """Verbatim Odoo install fault for ``BackgroundJob.error`` when sandbox failed."""
    if not isinstance(result, dict):
        return None
    nested = result.get("sandbox") if isinstance(result.get("sandbox"), dict) else {}
    ok = result.get("ok")
    if ok is None:
        ok = nested.get("ok")
    if ok is not False:
        return None
    msg = str(result.get("message") or nested.get("message") or "")
    tail = str(result.get("log_tail") or nested.get("log_tail") or "")
    text = verbatim_sandbox_error_text(message=msg, log_tail=tail).strip()
    return text or None

def _coerce_sandbox_major(major: int | str | None) -> int:
    """Accept 19, ``'19.0'``, ``'19.0+e'``; empty/unparseable → 19."""
    if major is None or isinstance(major, bool):
        return 19
    if isinstance(major, int):
        return major
    text = str(major).strip()
    if not text:
        return 19
    core = text.split("+", 1)[0].split("-", 1)[0]
    major_s = core.split(".", 1)[0]
    if major_s.isdigit():
        return int(major_s)
    return 19


def resolve_sandbox_major(major: int | str | None) -> int:
    """Normalize major for ephemeral sandbox; default 19.

    Connection ``server_version`` is stored as ``'19.0'`` / ``'19.0+e'``. Callers
    that pass that string must not hit ``int('19.0')`` (ValueError → HTTP 500).
    """
    m = _coerce_sandbox_major(major)
    if m not in SUPPORTED_SANDBOX_MAJORS:
        raise ValueError(
            f"Sandbox major {m} unsupported; allowed: {sorted(SUPPORTED_SANDBOX_MAJORS)}"
        )
    return m


def sandbox_major_for_connection(server_version: int | str | None) -> int:
    """Best-effort sandbox/export major from a stored Odoo version; never raises."""
    try:
        return resolve_sandbox_major(server_version)
    except (ValueError, TypeError):
        return 19


def sandbox_image_for_major(major: int) -> str:
    return f"odoo:{resolve_sandbox_major(major)}"


def sandbox_docker_status() -> tuple[bool, str]:
    """Return whether ephemeral sandbox Docker is usable from this process."""
    from app.settings import settings

    socket_path = settings.sandbox_docker_socket.strip()
    if socket_path.lower() in {"off", "false", "0", "disabled"}:
        return False, "Sandbox Docker explicitly disabled (SANDBOX_DOCKER_SOCKET=off)."
    if socket_path:
        if not Path(socket_path).exists():
            return False, f"SANDBOX_DOCKER_SOCKET path not found: {socket_path}"
    elif Path("/.dockerenv").exists():
        return False, (
            "Sandbox Docker is disabled in the containerized API (SANDBOX_DOCKER_SOCKET unset). "
            "Mount the host Docker socket and set SANDBOX_DOCKER_SOCKET=/var/run/docker.sock "
            "to run ephemeral sandbox validation from a containerized API."
        )
    if shutil.which("docker") is None:
        return False, "Docker CLI is not available in the API runtime"
    return True, "ok"


def _compose(
    *args: str,
    check: bool = True,
    odoo_major: int = 19,
    job_id: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "ODOO_SANDBOX_IMAGE": sandbox_image_for_major(odoo_major),
    }
    cmd = [
        "docker",
        "compose",
        "-p",
        "odoo-sandbox",
        "-f",
        str(SANDBOX_COMPOSE),
        *args,
    ]
    logger.info("sandbox: %s (image=%s)", " ".join(cmd), env["ODOO_SANDBOX_IMAGE"])
    if job_id:
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        _sandbox_subprocesses[job_id] = proc
        try:
            stdout, stderr = proc.communicate()
            cp = subprocess.CompletedProcess(cmd, proc.returncode or 0, stdout, stderr)
            if check and cp.returncode != 0:
                raise subprocess.CalledProcessError(cp.returncode, cmd, cp.stdout, cp.stderr)
            return cp
        finally:
            _sandbox_subprocesses.pop(job_id, None)
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


def _extract_zip(zip_bytes: bytes, dest: Path) -> str:
    """Extract addon zip into dest; return technical module folder name."""
    validate_zip_bytes(zip_bytes)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        if not names:
            raise ValueError("Empty zip")
        top = names[0].split("/")[0]
        safe_extract(zf, dest)
        module_dir = dest / top
        if not (module_dir / "__manifest__.py").exists():
            raise ValueError(f"Zip missing {top}/__manifest__.py")
        return top


def _wait_http(url: str, timeout_s: float = 120) -> None:
    import urllib.request

    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=5)  # noqa: S310 — local sandbox
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2)
    raise TimeoutError(f"Sandbox Odoo not ready at {url}: {last_err}")


def _drop_sandbox_db() -> None:
    subprocess.run(
        [
            "docker",
            "exec",
            DB_CONTAINER,
            "psql",
            "-U",
            "odoo",
            "-d",
            "postgres",
            "-c",
            (
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname='{SANDBOX_DB}' AND pid <> pg_backend_pid();"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "docker",
            "exec",
            DB_CONTAINER,
            "psql",
            "-U",
            "odoo",
            "-d",
            "postgres",
            "-c",
            f'DROP DATABASE IF EXISTS "{SANDBOX_DB}";',
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _init_db(odoo_major: int) -> None:
    """Create sandbox_test. Odoo 19 uses ``odoo db init``; ≤18 uses classic -i base,web."""
    if odoo_major >= 19:
        subprocess.run(
            [
                "docker",
                "exec",
                ODOO_CONTAINER,
                "odoo",
                "db",
                "--db_host=db",
                "-r",
                "odoo",
                "-w",
                "odoo",
                "init",
                "--username",
                SANDBOX_USER,
                "--password",
                SANDBOX_PASSWORD,
                "--force",
                SANDBOX_DB,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return

    # Avoid KeyError ir.http: stop worker, drop DB, one-shot init, start worker.
    _compose("stop", "odoo", check=False, odoo_major=odoo_major)
    _drop_sandbox_db()
    _compose(
        "run",
        "--rm",
        "--no-deps",
        "odoo",
        "odoo",
        "--db_host=db",
        "-r",
        "odoo",
        "-w",
        "odoo",
        "-d",
        SANDBOX_DB,
        "-i",
        "base,web",
        "--without-demo=all",
        "--stop-after-init",
        "--load-language=en_US",
        check=True,
        odoo_major=odoo_major,
    )
    _compose("start", "odoo", check=True, odoo_major=odoo_major)


def _sandbox_client(expected_major: int = 19) -> Any:
    """Connected ``OdooClient`` for the ephemeral sandbox (XML-RPC; admin password).

    Forced ``rpc_protocol=xmlrpc`` so local Docker admin/admin keeps working —
    External JSON-2 requires an API key and must not break sandbox installs.
    """
    from odoo_client import ConnectionConfig, OdooClient

    client = OdooClient(
        ConnectionConfig(
            url=SANDBOX_URL,
            db=SANDBOX_DB,
            username=SANDBOX_USER,
            password=SANDBOX_PASSWORD,
            rpc_protocol="xmlrpc",
        )
    )
    client.connect()
    if int(client.capabilities.major) != int(expected_major):
        raise RuntimeError(
            f"Sandbox not Odoo {expected_major}: major={client.capabilities.major!r}"
        )
    return client


class _LegacyExecuteKwProxy:
    """Compat shim for ``after_install(uid, models, major)`` hooks.

    Historical hooks call ``models.execute_kw(db, uid, password, model, method, args, kw)``.
    Route those through ``OdooClient.execute_kw`` without changing hook call sites.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    def execute_kw(
        self,
        _db: str,
        _uid: int,
        _password: str,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        return self._client.execute_kw(model, method, args or [], kwargs or {})


def _sandbox_rpc(expected_major: int = 19) -> tuple[int, _LegacyExecuteKwProxy]:
    """Return ``(uid, models_proxy)`` — same shape as the old ServerProxy pair."""
    client = _sandbox_client(expected_major)
    return int(client.uid), _LegacyExecuteKwProxy(client)


def _install_module_rpc(module_name: str, *, odoo_major: int) -> None:
    client = _sandbox_client(odoo_major)
    client.execute_kw("ir.module.module", "update_list", [])
    rows = client.execute_kw(
        "ir.module.module",
        "search_read",
        [[("name", "=", module_name)]],
        {"fields": ["id", "state"], "limit": 1},
    )
    if not rows:
        raise RuntimeError(f"Module {module_name!r} not found after update_list")
    if rows[0]["state"] == "installed":
        return
    client.execute_kw(
        "ir.module.module",
        "button_immediate_install",
        [[rows[0]["id"]]],
    )
    refreshed = client.execute_kw(
        "ir.module.module",
        "read",
        [[rows[0]["id"]]],
        {"fields": ["state"]},
    )
    if not refreshed or refreshed[0]["state"] != "installed":
        raise RuntimeError(f"Module {module_name!r} failed to install (state={refreshed})")


def _ensure_modules_installed(
    module_names: list[str], *, odoo_major: int = 19
) -> list[str]:
    """Install listed modules via update_list + button_immediate_install.

    Returns technical names that were newly installed (skips already installed).
    """
    cleaned = [m.strip() for m in module_names if m and m.strip()]
    if not cleaned:
        return []

    client = _sandbox_client(odoo_major)
    client.execute_kw("ir.module.module", "update_list", [])

    newly: list[str] = []
    for name in cleaned:
        rows = client.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", name)]],
            {"fields": ["id", "state"], "limit": 1},
        )
        if not rows:
            raise RuntimeError(f"Extra module {name!r} not found after update_list")
        if rows[0]["state"] == "installed":
            continue
        client.execute_kw(
            "ir.module.module",
            "button_immediate_install",
            [[rows[0]["id"]]],
        )
        refreshed = client.execute_kw(
            "ir.module.module",
            "read",
            [[rows[0]["id"]]],
            {"fields": ["state"]},
        )
        if not refreshed or refreshed[0]["state"] != "installed":
            raise RuntimeError(f"Extra module {name!r} failed to install (state={refreshed})")
        newly.append(name)
    return newly


def _resolve_extra_modules(extra_modules: list[str] | None) -> list[str]:
    if extra_modules is not None:
        return [m.strip() for m in extra_modules if m and m.strip()]
    from app.settings import settings

    return settings.sandbox_extra_module_list()


def build_test_enable_argv(module: str, *, odoo_major: int = 19) -> list[str]:
    """Argv for ``odoo … -u MODULE --test-enable --stop-after-init`` (PR-D).

    ``odoo_major`` reserved for future flag drift; argv shape is shared 16–19 CE.
    """
    _ = odoo_major
    technical = (module or "").strip()
    if not technical:
        raise ValueError("module name required for --test-enable")
    return [
        "odoo",
        "--db_host=db",
        "-r",
        "odoo",
        "-w",
        "odoo",
        "-d",
        SANDBOX_DB,
        "-u",
        technical,
        "--test-enable",
        "--stop-after-init",
    ]


def parse_odoo_test_output(output: str) -> list[str]:
    """Extract parseable FAIL/ERROR lines (and summary counts) from Odoo test logs."""
    text = output or ""
    failures: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _TEST_FAIL_LINE_RE.match(line)
        if m:
            row = f"{m.group(1).upper()}: {m.group(2).strip()}"
            key = row.lower()
            if key not in seen:
                seen.add(key)
                failures.append(row)
            continue
        summary = _TEST_SUMMARY_FAIL_RE.search(line)
        if summary:
            failed = int(summary.group(1) or summary.group(3) or 0)
            errors = int(summary.group(2) or summary.group(4) or 0)
            if failed or errors:
                row = f"SUMMARY: {failed} failed, {errors} error(s)"
                key = row.lower()
                if key not in seen:
                    seen.add(key)
                    failures.append(row)
    return failures[:40]


def _run_module_tests(
    module: str,
    *,
    odoo_major: int,
    job_id: str | None = None,
) -> tuple[bool, str, list[str]]:
    """Run ``--test-enable`` against the live sandbox DB. Returns (ok, log, failures)."""
    argv = build_test_enable_argv(module, odoo_major=odoo_major)
    # compose exec into the already-up odoo service (DB + addons volume mounted).
    cp = _compose(
        "exec",
        "-T",
        "odoo",
        *argv,
        check=False,
        odoo_major=odoo_major,
        job_id=job_id,
    )
    combined = "\n".join(
        part for part in (cp.stdout or "", cp.stderr or "") if part
    ).strip()
    failures = parse_odoo_test_output(combined)
    if cp.returncode != 0 and not failures:
        failures = [
            f"test-enable exited {cp.returncode} "
            f"(no FAIL/ERROR lines parsed — see log_tail)"
        ]
    ok = cp.returncode == 0 and not failures
    return ok, combined[-8000:], failures


def run_sandbox_install(
    zip_bytes: bytes,
    *,
    module_name: str | None = None,
    keep_alive: bool = False,
    extra_modules: list[str] | None = None,
    odoo_major: int | None = None,
    job_id: str | None = None,
    after_install: object | None = None,
    run_tests: bool = False,
) -> SandboxResult:
    """Install zip in ephemeral sandbox. Serialized — only one run at a time.

    ``odoo_major``: Docker image ``odoo:{major}`` (default 19). Must match the
    connection / export target for honest validation.

    ``extra_modules``: if provided, install these after DB init before the candidate.
    If ``None``, use ``settings.sandbox_extra_modules`` / ``SANDBOX_EXTRA_MODULES``.

    ``after_install``: optional ``callable(uid, models, odoo_major)`` run while the
    sandbox is still up (Option A PDF/RPC smoke). Exceptions fail the run.

    ``run_tests``: when True, after RPC install run ``odoo -u MODULE --test-enable
    --stop-after-init`` (PR-D). Default False so fast CI / in-loop iteration stays
    Docker-light; nightly / prove bar (PR-E) must pass with ``run_tests=True``.
    """
    from app.ai_structural_zip_gate import structural_zip_gate

    gate = structural_zip_gate(zip_bytes)
    if not gate.get("ok"):
        detail = "; ".join(gate.get("findings") or ["structural zip gate failed"])
        return SandboxResult(
            ok=False,
            module=module_name or "unknown",
            message=f"Structural zip gate failed: {detail}",
            odoo_major=odoo_major,
        )

    if not SANDBOX_COMPOSE.exists():
        raise FileNotFoundError(f"Missing {SANDBOX_COMPOSE}")

    docker_ok, docker_detail = sandbox_docker_status()
    if not docker_ok:
        return SandboxResult(
            ok=False,
            module=module_name or "unknown",
            message=docker_detail,
            odoo_major=odoo_major,
        )

    try:
        major = resolve_sandbox_major(odoo_major)
    except ValueError as exc:
        return SandboxResult(
            ok=False,
            module=module_name or "unknown",
            message=str(exc),
            odoo_major=odoo_major,
        )

    acquired = _sandbox_lock.acquire(blocking=True, timeout=900)
    if not acquired:
        return SandboxResult(
            ok=False,
            module=module_name or "unknown",
            message="Sandbox is busy — another validation is still running (timeout waiting for lock)",
            odoo_major=major,
        )

    try:
        return _run_sandbox_install_unlocked(
            zip_bytes,
            module_name=module_name,
            keep_alive=keep_alive,
            extra_modules=extra_modules,
            odoo_major=major,
            job_id=job_id,
            after_install=after_install,
            run_tests=run_tests,
        )
    finally:
        _sandbox_lock.release()


def _run_sandbox_install_unlocked(
    zip_bytes: bytes,
    *,
    module_name: str | None = None,
    keep_alive: bool = False,
    extra_modules: list[str] | None = None,
    odoo_major: int = 19,
    job_id: str | None = None,
    after_install: object | None = None,
    run_tests: bool = False,
) -> SandboxResult:
    global _active_sandbox_job_id
    from app.jobs import job_cancelled

    _active_sandbox_job_id = job_id
    logs: list[str] = []
    technical = module_name or "unknown"
    try:
        if job_id and job_cancelled(job_id):
            return SandboxResult(
                ok=False,
                module=technical,
                message="Sandbox cancelled",
                odoo_major=odoo_major,
            )
        technical = _extract_zip(zip_bytes, SANDBOX_ADDONS)
        logs.append(
            f"extracted {technical} into {SANDBOX_ADDONS} "
            f"(target major={odoo_major}, image={sandbox_image_for_major(odoo_major)})"
        )

        down = _compose("down", "-v", check=False, odoo_major=odoo_major, job_id=job_id)
        logs.append(down.stdout[-500:] if down.stdout else down.stderr[-500:])

        up = _compose("up", "-d", odoo_major=odoo_major, job_id=job_id)
        logs.append(up.stdout[-500:] if up.stdout else "")

        _wait_http(f"{SANDBOX_URL}/web/login", timeout_s=180)
        logs.append("http ready")

        _init_db(odoo_major)
        logs.append(f"db initialized (major={odoo_major})")

        if odoo_major >= 19:
            _compose("restart", "odoo", check=False, odoo_major=odoo_major)
        _wait_http(f"{SANDBOX_URL}/web/login", timeout_s=150)

        extras = _resolve_extra_modules(extra_modules)
        if extras:
            newly = _ensure_modules_installed(extras, odoo_major=odoo_major)
            logs.append(
                f"extra modules requested={extras}; newly_installed={newly or 'none (already present)'}"
            )

        _install_module_rpc(technical, odoo_major=odoo_major)
        logs.append(f"installed {technical}")

        if callable(after_install):
            uid, models = _sandbox_rpc(odoo_major)
            after_install(uid, models, odoo_major)
            logs.append("after_install hook ok")

        test_failures: list[str] = []
        tests_ran = False
        if run_tests:
            tests_ran = True
            test_ok, test_log, test_failures = _run_module_tests(
                technical, odoo_major=odoo_major, job_id=job_id
            )
            if test_log:
                logs.append(test_log)
            if not test_ok:
                detail = "; ".join(test_failures[:5]) or "unknown test failure"
                return SandboxResult(
                    ok=False,
                    module=technical,
                    message=f"Sandbox tests failed for {technical}: {detail}",
                    log_tail=_join_sandbox_logs(logs),
                    sandbox_url=SANDBOX_URL if keep_alive else None,
                    odoo_major=odoo_major,
                    test_failures=test_failures,
                    tests_ran=True,
                )
            logs.append(f"test-enable ok for {technical}")

        extra_msg = ""
        if extras:
            extra_msg = f" (preloaded {', '.join(extras)})"
        test_msg = " + tests" if tests_ran else ""
        return SandboxResult(
            ok=True,
            module=technical,
            message=(
                f"Sandbox (Odoo {odoo_major}) installed {technical} "
                f"successfully{extra_msg}{test_msg}"
            ),
            log_tail=_join_sandbox_logs(logs),
            sandbox_url=SANDBOX_URL if keep_alive else None,
            odoo_major=odoo_major,
            test_failures=[],
            tests_ran=tests_ran,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("sandbox install failed")
        return SandboxResult(
            ok=False,
            module=technical,
            message=str(exc),
            log_tail=_join_sandbox_logs(logs),
            sandbox_url=None,
            odoo_major=odoo_major,
        )
    finally:
        _active_sandbox_job_id = None
        if not keep_alive:
            try:
                _compose("down", "-v", check=False, odoo_major=odoo_major)
            except Exception:  # noqa: BLE001
                logger.warning("sandbox teardown failed", exc_info=True)
            if SANDBOX_ADDONS.exists():
                for child in SANDBOX_ADDONS.iterdir():
                    if child.name == ".gitkeep":
                        continue
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)

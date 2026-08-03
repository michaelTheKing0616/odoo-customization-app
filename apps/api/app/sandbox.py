"""Phase 6 — ephemeral Docker Odoo sandbox that installs a generated module zip.

Matching-major: image is ``odoo:{16|17|18|19}`` from the connection (or explicit
``odoo_major``). Serialized via a process lock — one sandbox at a time.
Host port **18069** (avoids clash with permanent Odoo 18 on 8070).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
import xmlrpc.client
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

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


def cancel_sandbox_if_running(job_id: str) -> None:
    """Tear down ephemeral sandbox when a background job is cancelled."""
    global _active_sandbox_job_id
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


def resolve_sandbox_major(major: int | None) -> int:
    """Normalize major for ephemeral sandbox; default 19."""
    m = 19 if major is None else int(major)
    if m not in SUPPORTED_SANDBOX_MAJORS:
        raise ValueError(
            f"Sandbox major {m} unsupported; allowed: {sorted(SUPPORTED_SANDBOX_MAJORS)}"
        )
    return m


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


def _sandbox_rpc(expected_major: int = 19) -> tuple[int, xmlrpc.client.ServerProxy]:
    common = xmlrpc.client.ServerProxy(f"{SANDBOX_URL}/xmlrpc/2/common", allow_none=True)
    version = common.version()
    server_version = str(version.get("server_version", ""))
    if not server_version.startswith(str(expected_major)):
        raise RuntimeError(
            f"Sandbox not Odoo {expected_major}: server_version={server_version!r}"
        )
    uid = common.authenticate(SANDBOX_DB, SANDBOX_USER, SANDBOX_PASSWORD, {})
    if not uid:
        raise RuntimeError("Sandbox auth failed")
    models = xmlrpc.client.ServerProxy(f"{SANDBOX_URL}/xmlrpc/2/object", allow_none=True)
    return uid, models


def _install_module_rpc(module_name: str, *, odoo_major: int) -> None:
    uid, models = _sandbox_rpc(odoo_major)
    models.execute_kw(
        SANDBOX_DB,
        uid,
        SANDBOX_PASSWORD,
        "ir.module.module",
        "update_list",
        [],
    )
    rows = models.execute_kw(
        SANDBOX_DB,
        uid,
        SANDBOX_PASSWORD,
        "ir.module.module",
        "search_read",
        [[("name", "=", module_name)]],
        {"fields": ["id", "state"], "limit": 1},
    )
    if not rows:
        raise RuntimeError(f"Module {module_name!r} not found after update_list")
    if rows[0]["state"] == "installed":
        return
    models.execute_kw(
        SANDBOX_DB,
        uid,
        SANDBOX_PASSWORD,
        "ir.module.module",
        "button_immediate_install",
        [[rows[0]["id"]]],
    )
    refreshed = models.execute_kw(
        SANDBOX_DB,
        uid,
        SANDBOX_PASSWORD,
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

    uid, models = _sandbox_rpc(odoo_major)
    models.execute_kw(
        SANDBOX_DB,
        uid,
        SANDBOX_PASSWORD,
        "ir.module.module",
        "update_list",
        [],
    )

    newly: list[str] = []
    for name in cleaned:
        rows = models.execute_kw(
            SANDBOX_DB,
            uid,
            SANDBOX_PASSWORD,
            "ir.module.module",
            "search_read",
            [[("name", "=", name)]],
            {"fields": ["id", "state"], "limit": 1},
        )
        if not rows:
            raise RuntimeError(f"Extra module {name!r} not found after update_list")
        if rows[0]["state"] == "installed":
            continue
        models.execute_kw(
            SANDBOX_DB,
            uid,
            SANDBOX_PASSWORD,
            "ir.module.module",
            "button_immediate_install",
            [[rows[0]["id"]]],
        )
        refreshed = models.execute_kw(
            SANDBOX_DB,
            uid,
            SANDBOX_PASSWORD,
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


def run_sandbox_install(
    zip_bytes: bytes,
    *,
    module_name: str | None = None,
    keep_alive: bool = False,
    extra_modules: list[str] | None = None,
    odoo_major: int | None = None,
    job_id: str | None = None,
) -> SandboxResult:
    """Install zip in ephemeral sandbox. Serialized — only one run at a time.

    ``odoo_major``: Docker image ``odoo:{major}`` (default 19). Must match the
    connection / export target for honest validation.

    ``extra_modules``: if provided, install these after DB init before the candidate.
    If ``None``, use ``settings.sandbox_extra_modules`` / ``SANDBOX_EXTRA_MODULES``.
    """
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

        down = _compose("down", "-v", check=False, odoo_major=odoo_major)
        logs.append(down.stdout[-500:] if down.stdout else down.stderr[-500:])

        up = _compose("up", "-d", odoo_major=odoo_major)
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

        extra_msg = ""
        if extras:
            extra_msg = f" (preloaded {', '.join(extras)})"
        return SandboxResult(
            ok=True,
            module=technical,
            message=(
                f"Sandbox (Odoo {odoo_major}) installed {technical} successfully{extra_msg}"
            ),
            log_tail="\n".join(logs)[-4000:],
            sandbox_url=SANDBOX_URL if keep_alive else None,
            odoo_major=odoo_major,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("sandbox install failed")
        return SandboxResult(
            ok=False,
            module=technical,
            message=str(exc),
            log_tail="\n".join(logs)[-4000:],
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

"""Sparse git checkout of odoo/odoo source files for Expert RAG (l10n + address data)."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from app.expert.fetcher import SUPPORTED_VERSIONS

logger = logging.getLogger(__name__)

ODOO_REPO = "https://github.com/odoo/odoo.git"
BASE_STATE_CSV = "odoo/addons/base/data/res.country.state.csv"
_PRIORITY_L10N_MANIFESTS = (
    "l10n_jo",
    "l10n_kw",
    "l10n_ae",
    "l10n_sa",
    "l10n_bh",
    "l10n_om",
    "l10n_qa",
    "l10n_lb",
    "l10n_eg",
)


def odoo_source_cache_dir(version: str) -> Path:
    from app.expert.fetcher import cache_root

    major, minor = version.split(".", 1)
    return cache_root() / f"odoo_src_{major}_{minor}"


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def _ensure_repo(version: str, *, offline: bool = False) -> Path:
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"Unsupported Odoo source version: {version}")

    dest = odoo_source_cache_dir(version)
    if offline:
        if (dest / ".git").is_dir():
            return dest
        raise FileNotFoundError(f"Offline mode: odoo source cache missing for {version} at {dest}")

    dest.mkdir(parents=True, exist_ok=True)
    git_dir = dest / ".git"
    if not git_dir.is_dir():
        logger.info("Cloning %s branch %s (sparse, for l10n/source ingest)", ODOO_REPO, version)
        cp = _run(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                "--depth",
                "1",
                "-b",
                version,
                ODOO_REPO,
                str(dest),
            ]
        )
        if cp.returncode != 0:
            raise RuntimeError(f"git clone odoo/odoo failed: {cp.stderr.strip() or cp.stdout.strip()}")

    _run(["git", "fetch", "origin", version, "--depth", "1"], cwd=dest)
    cp = _run(["git", "reset", "--hard", f"origin/{version}"], cwd=dest)
    if cp.returncode != 0:
        _run(["git", "checkout", version], cwd=dest)
    return dest


def _list_l10n_state_paths(repo: Path) -> list[str]:
    cp = _run(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=repo)
    if cp.returncode != 0:
        return []
    paths: list[str] = []
    for line in cp.stdout.splitlines():
        name = line.strip()
        if not name.startswith("addons/l10n_"):
            continue
        if name.endswith("res.country.state.csv") or name.endswith("res_country_data.xml"):
            paths.append(name)
    return sorted(set(paths))


def fetch_odoo_source_paths(version: str, *, offline: bool = False) -> list[Path]:
    """Materialize base state CSV + l10n state/country data files for ``version``."""
    repo = _ensure_repo(version, offline=offline)
    candidates: set[str] = {BASE_STATE_CSV}
    candidates.update(_list_l10n_state_paths(repo))
    for mod in _PRIORITY_L10N_MANIFESTS:
        candidates.add(f"addons/{mod}/__manifest__.py")

    _run(["git", "sparse-checkout", "init", "--no-cone"], cwd=repo)
    materialized: list[Path] = []
    for rel in sorted(candidates):
        cp = _run(["git", "checkout", version, "--", rel], cwd=repo)
        if cp.returncode != 0:
            logger.debug("Skipping missing odoo source path %s on %s", rel, version)
            continue
        path = repo / rel
        if path.is_file():
            materialized.append(path)

    if not any(p.as_posix().endswith("res.country.state.csv") for p in materialized):
        raise RuntimeError(f"{BASE_STATE_CSV} not available for Odoo {version}")

    manifest = repo / ".expert_odoo_source_manifest.json"
    manifest.write_text(
        json.dumps(
            {"version": version, "files": [str(p.relative_to(repo)) for p in materialized]},
            indent=2,
        ),
        encoding="utf-8",
    )
    return materialized

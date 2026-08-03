"""Sparse git checkout of odoo/documentation content/ for Expert RAG ingest."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

DOC_REPO = "https://github.com/odoo/documentation.git"
SUPPORTED_VERSIONS = ("16.0", "17.0", "18.0", "19.0")
SPARSE_PATH = "content"


def cache_root() -> Path:
    root = Path(__file__).resolve().parents[4] / ".cache" / "expert"
    root.mkdir(parents=True, exist_ok=True)
    return root


def version_cache_dir(version: str) -> Path:
    return cache_root() / f"odoo_docs_{version.replace('.', '_')}"


def manifest_path(version: str) -> Path:
    return version_cache_dir(version) / ".expert_manifest.json"


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def fetch_documentation(version: str, *, offline: bool = False) -> Path:
    """Ensure odoo/documentation content/ for ``version`` is available locally."""
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"Unsupported documentation version: {version}")

    dest = version_cache_dir(version)
    content_dir = dest / SPARSE_PATH
    if offline:
        if content_dir.is_dir():
            return content_dir
        raise FileNotFoundError(
            f"Offline mode: cached documentation missing for {version} at {content_dir}"
        )

    dest.mkdir(parents=True, exist_ok=True)
    git_dir = dest / ".git"

    if not git_dir.is_dir():
        logger.info("Cloning %s branch %s (sparse content/)", DOC_REPO, version)
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
                DOC_REPO,
                str(dest),
            ]
        )
        if cp.returncode != 0:
            raise RuntimeError(f"git clone failed: {cp.stderr.strip() or cp.stdout.strip()}")

    _run(["git", "fetch", "origin", version, "--depth", "1"], cwd=dest)
    _run(["git", "checkout", version], cwd=dest)
    _run(["git", "sparse-checkout", "init", "--cone"], cwd=dest)
    _run(["git", "sparse-checkout", "set", SPARSE_PATH], cwd=dest)
    cp = _run(["git", "pull", "origin", version, "--depth", "1"], cwd=dest)
    if cp.returncode != 0:
        raise RuntimeError(f"git pull failed: {cp.stderr.strip() or cp.stdout.strip()}")

    if not content_dir.is_dir():
        raise RuntimeError(f"Sparse checkout did not produce {content_dir}")

    manifest_path(version).write_text(
        json.dumps({"version": version, "content_dir": str(content_dir)}, indent=2),
        encoding="utf-8",
    )
    return content_dir


def iter_doc_files(content_dir: Path) -> list[Path]:
    """Return RST/MD files under the documentation content tree."""
    files: list[Path] = []
    for pattern in ("**/*.rst", "**/*.md"):
        files.extend(sorted(content_dir.glob(pattern)))
    return files

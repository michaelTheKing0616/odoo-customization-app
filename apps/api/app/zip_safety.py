"""Zip archive safety checks (size limits, zip-bomb, zip-slip)."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

MAX_ZIP_BYTES = 25 * 1024 * 1024  # 25 MiB compressed
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MiB uncompressed sum
MAX_FILES = 2000


def _reject_unsafe_member_name(name: str) -> None:
    """Raise ValueError if a zip member path is absolute or contains ``..``."""
    if not name or name.strip() == "":
        raise ValueError("Zip-slip: empty member path rejected")
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//"):
        raise ValueError(f"Zip-slip: absolute path rejected ({name!r})")
    # Windows-style absolute (C:/..., \\server\share)
    path = Path(name)
    if path.is_absolute():
        raise ValueError(f"Zip-slip: absolute path rejected ({name!r})")
    if any(part == ".." for part in Path(normalized).parts):
        raise ValueError(f"Zip-slip: path traversal rejected ({name!r})")


def validate_zip_bytes(zip_bytes: bytes) -> None:
    """Validate compressed size, file count, uncompressed sum, and member paths.

    Raises:
        ValueError: with a clear message for empty, oversized, zip-bomb, or zip-slip.
    """
    if not zip_bytes:
        raise ValueError("Empty zip")
    if len(zip_bytes) > MAX_ZIP_BYTES:
        raise ValueError(
            f"Zip too large (compressed): {len(zip_bytes)} bytes exceeds {MAX_ZIP_BYTES}"
        )
    try:
        zf_ctx = zipfile.ZipFile(BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid zip: {exc}") from exc

    with zf_ctx as zf:
        infos = zf.infolist()
        if not infos:
            raise ValueError("Empty zip")
        if len(infos) > MAX_FILES:
            raise ValueError(f"Too many files in zip: {len(infos)} exceeds {MAX_FILES}")
        total_uncompressed = 0
        for info in infos:
            _reject_unsafe_member_name(info.filename)
            total_uncompressed += max(0, info.file_size)
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise ValueError(
                    "Zip-bomb: uncompressed size "
                    f"{total_uncompressed} exceeds {MAX_UNCOMPRESSED_BYTES}"
                )


def safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract zip members only if each resolved path stays under ``dest``."""
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for info in zf.infolist():
        _reject_unsafe_member_name(info.filename)
        target = (dest / info.filename).resolve()
        try:
            target.relative_to(dest)
        except ValueError as exc:
            raise ValueError(
                f"Zip-slip: path escapes destination ({info.filename!r})"
            ) from exc
        zf.extract(info, dest)

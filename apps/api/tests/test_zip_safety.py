"""Unit tests for zip size / zip-slip / zip-bomb guards."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.zip_safety import MAX_ZIP_BYTES, validate_zip_bytes


def _tiny_valid_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("demo_mod/__manifest__.py", "{'name': 'Demo'}\n")
        zf.writestr("demo_mod/__init__.py", "")
    return buf.getvalue()


def test_valid_tiny_zip_ok() -> None:
    validate_zip_bytes(_tiny_valid_zip())


def test_path_with_dotdot_rejected() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", "nope")
    with pytest.raises(ValueError, match="[Zz]ip-slip|traversal"):
        validate_zip_bytes(buf.getvalue())


def test_oversized_compressed_rejected() -> None:
    huge = b"PK" + b"x" * (MAX_ZIP_BYTES + 1)
    with pytest.raises(ValueError, match="too large"):
        validate_zip_bytes(huge)


def test_absolute_path_member_rejected() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo("/tmp/evil.txt")
        zf.writestr(info, "nope")
    with pytest.raises(ValueError, match="[Zz]ip-slip|absolute"):
        validate_zip_bytes(buf.getvalue())


def test_safe_extract_keeps_members_under_dest(tmp_path: Path) -> None:
    from app.zip_safety import safe_extract

    raw = _tiny_valid_zip()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        safe_extract(zf, tmp_path)
    assert (tmp_path / "demo_mod" / "__manifest__.py").is_file()

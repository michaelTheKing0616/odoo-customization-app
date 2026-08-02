"""Extract model technical names from a generated Odoo module zip."""

from __future__ import annotations

import re
import zipfile
from io import BytesIO


_NAME_RE = re.compile(r"""_name\s*=\s*['"]([^'"]+)['"]""")
_MODEL_FIELD_RE = re.compile(
    r"""<field\s+name=["']model["']\s*>([^<]+)</field>""",
    re.IGNORECASE,
)


def extract_model_names_from_zip(zip_bytes: bytes) -> list[str]:
    """Best-effort parse of Python `_name` and data-mode ir.model XML."""
    found: list[str] = []
    seen: set[str] = set()
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for path in zf.namelist():
            norm = path.replace("\\", "/")
            if norm.endswith(".py") and "/models/" in norm and not norm.endswith("__init__.py"):
                try:
                    text = zf.read(path).decode("utf-8", errors="ignore")
                except Exception:  # noqa: BLE001
                    continue
                for match in _NAME_RE.finditer(text):
                    name = match.group(1).strip()
                    if name and name not in seen:
                        seen.add(name)
                        found.append(name)
            if norm.endswith(".xml") and (
                "/data/models.xml" in norm or norm.endswith("models.xml")
            ):
                try:
                    text = zf.read(path).decode("utf-8", errors="ignore")
                except Exception:  # noqa: BLE001
                    continue
                for match in _MODEL_FIELD_RE.finditer(text):
                    name = match.group(1).strip()
                    if name and name not in seen:
                        seen.add(name)
                        found.append(name)
    return found

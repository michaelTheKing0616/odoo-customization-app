"""Build Expert chunks from odoo/odoo localization source files."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from app.expert.chunker import DocChunk

_COUNTRY_NAMES: dict[str, str] = {
    "jo": "Jordan",
    "kw": "Kuwait",
    "ae": "United Arab Emirates",
    "sa": "Saudi Arabia",
    "bh": "Bahrain",
    "om": "Oman",
    "qa": "Qatar",
    "lb": "Lebanon",
    "eg": "Egypt",
    "us": "United States",
}


def _country_label(code: str) -> str:
    return _COUNTRY_NAMES.get(code.lower(), code.upper())


def chunk_res_country_state_csv(path: Path, *, version: str) -> list[DocChunk]:
    """Group ``res.country.state.csv`` rows by country into retrieval chunks."""
    if not path.is_file():
        return []

    by_country: dict[str, list[tuple[str, str, str]]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 4:
                continue
            _ext_id, country_code, name, code = row[0], row[1].strip().lower(), row[2], row[3]
            if not country_code or country_code == "country_code":
                continue
            by_country.setdefault(country_code, []).append((name, code, _ext_id))

    chunks: list[DocChunk] = []
    for country_code in sorted(by_country):
        rows = by_country[country_code]
        label = _country_label(country_code)
        lines = [
            f"Odoo {version} ships the following **States / Provinces** (`res.country.state`) "
            f"for **{label}** (`{country_code}`) in `base` data:",
            "",
        ]
        for name, code, ext_id in rows:
            lines.append(f"- **{name}** — xml id `{ext_id}`, code `{code}`")
        lines.extend(
            [
                "",
                "These appear in **Contacts → Configuration → Localization → Fed. States** "
                f"when country is {label}. Partner address forms show the **State** dropdown "
                "when states exist for the selected country.",
                "",
                "Governorates and administrative regions are modeled as `res.country.state` rows "
                "linked to `res.country`. Names follow Odoo's shipped CSV — they may differ from "
                "local official names (e.g. **Amman** rather than **Capital Governorate** for Jordan).",
            ]
        )
        chunks.append(
            DocChunk(
                breadcrumb=f"Odoo Source > res.country.state > {label} ({country_code})",
                text="\n".join(lines),
                source_path=str(path),
            )
        )
    return chunks


def chunk_l10n_manifest(path: Path, *, version: str) -> list[DocChunk]:
    """Extract manifest summary for an l10n module."""
    if not path.name == "__manifest__.py" or not path.is_file():
        return []

    text = path.read_text(encoding="utf-8", errors="replace")
    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', text)
    summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', text)
    desc_match = re.search(r'"description"\s*:\s*"""(.*?)"""', text, re.S)
    module = path.parent.name
    title = name_match.group(1) if name_match else module
    summary = summary_match.group(1) if summary_match else ""
    description = (desc_match.group(1).strip() if desc_match else "").strip()
    body_parts = [
        f"**{title}** (`{module}`) — Odoo {version} Community localization module.",
    ]
    if summary:
        body_parts.append(summary)
    if description:
        body_parts.append(description[:1200])
    body_parts.append(
        "Install via Apps when fiscal/accounting localization is required for this country."
    )
    return [
        DocChunk(
            breadcrumb=f"Odoo Source > l10n > {module}",
            text="\n".join(body_parts),
            source_path=str(path),
        )
    ]


def chunks_from_odoo_source_files(paths: list[Path], *, version: str) -> list[DocChunk]:
    chunks: list[DocChunk] = []
    for path in paths:
        rel = path.as_posix()
        if rel.endswith("res.country.state.csv"):
            chunks.extend(chunk_res_country_state_csv(path, version=version))
        elif path.name == "__manifest__.py":
            chunks.extend(chunk_l10n_manifest(path, version=version))
    return chunks

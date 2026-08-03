"""Odoo Apps Store packaging readiness checker (TIER-3 / public manifest rules)."""

from __future__ import annotations

import ast
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Literal

CheckStatus = Literal["pass", "warn", "fail"]

STORE_REVIEW_DISCLAIMER = (
    "Review and approval are Odoo's process, on Odoo's timeline — this checklist "
    "only helps you prepare the package."
)

# Common ir.module.category names (public Odoo Apps taxonomy — best-effort allowlist).
ODOO_MODULE_CATEGORIES = frozenset(
    {
        "Sales",
        "Accounting",
        "Inventory",
        "Manufacturing",
        "Website",
        "Marketing",
        "Human Resources",
        "Productivity",
        "Customization",
        "Technical Settings",
        "Hidden",
        "Uncategorized",
        "Services",
        "Point of Sale",
        "Project",
        "Events",
        "Email Marketing",
        "Discuss",
        "Extra Tools",
    }
)

VALID_LICENSES = frozenset(
    {
        "LGPL-3",
        "AGPL-3",
        "OPL-1",
        "OEEL-1",
        "Other proprietary",
    }
)

VERSION_RE = re.compile(r"^\d+\.0\.\d+\.\d+\.\d+$")

# Minimal valid 1×1 PNG (placeholder icon — flagged as warn).
PLACEHOLDER_ICON_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


@dataclass
class StoreCheckItem:
    key: str
    label: str
    status: CheckStatus
    message: str


@dataclass
class StoreReadinessReport:
    ok: bool
    items: list[StoreCheckItem] = field(default_factory=list)
    fail_count: int = 0
    warn_count: int = 0
    disclaimer: str = STORE_REVIEW_DISCLAIMER
    message: str = ""

    def add(self, item: StoreCheckItem) -> None:
        self.items.append(item)
        if item.status == "fail":
            self.fail_count += 1
        elif item.status == "warn":
            self.warn_count += 1

    def finalize(self) -> StoreReadinessReport:
        self.ok = self.fail_count == 0
        if self.fail_count:
            self.message = f"{self.fail_count} store-readiness check(s) failed"
        elif self.warn_count:
            self.message = f"Ready with {self.warn_count} warning(s)"
        else:
            self.message = "Store-readiness checks passed"
        return self


def parse_manifest_py(content: str) -> dict[str, Any]:
    """Parse Odoo __manifest__.py dict (literal only)."""
    text = content.strip()
    if text.startswith("#"):
        text = text.split("\n", 1)[-1]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No dict literal in manifest")
    raw = match.group(0)
    return ast.literal_eval(raw)


def manifest_from_zip(zip_bytes: bytes, technical_name: str) -> dict[str, Any]:
    path = f"{technical_name}/__manifest__.py"
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        if path not in zf.namelist():
            raise ValueError(f"Missing {path}")
        content = zf.read(path).decode("utf-8")
    return parse_manifest_py(content)


def zip_member_names(zip_bytes: bytes) -> set[str]:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        return set(zf.namelist())


def check_store_readiness(
    *,
    manifest: dict[str, Any],
    zip_members: set[str],
    technical_name: str,
    major: int | None,
    icon_is_placeholder: bool = False,
) -> StoreReadinessReport:
    report = StoreReadinessReport(ok=True)

    name = str(manifest.get("name") or "").strip()
    if len(name) >= 3:
        report.add(StoreCheckItem("name", "Module name", "pass", f"Name: {name[:80]}"))
    else:
        report.add(StoreCheckItem("name", "Module name", "fail", "Manifest name is missing or too short"))

    summary = str(manifest.get("summary") or "").strip()
    if len(summary) >= 10:
        report.add(StoreCheckItem("summary", "Summary", "pass", summary[:120]))
    elif summary:
        report.add(StoreCheckItem("summary", "Summary", "warn", "Summary is shorter than 10 characters"))
    else:
        report.add(StoreCheckItem("summary", "Summary", "fail", "Manifest summary is required"))

    description = str(manifest.get("description") or "").strip()
    if len(description) >= 50:
        report.add(StoreCheckItem("description", "Description", "pass", f"{len(description)} characters"))
    elif description:
        report.add(
            StoreCheckItem(
                "description",
                "Description",
                "warn",
                f"Description is only {len(description)} characters — Apps listing usually needs more",
            )
        )
    else:
        report.add(StoreCheckItem("description", "Description", "fail", "Manifest description is required"))

    category = str(manifest.get("category") or "").strip()
    if category in ODOO_MODULE_CATEGORIES:
        report.add(StoreCheckItem("category", "Category", "pass", category))
    elif category:
        report.add(
            StoreCheckItem(
                "category",
                "Category",
                "warn",
                f"Category {category!r} is not in the known Apps category list",
            )
        )
    else:
        report.add(StoreCheckItem("category", "Category", "fail", "Manifest category is required"))

    version = str(manifest.get("version") or "").strip()
    if VERSION_RE.match(version):
        if major is not None and not version.startswith(f"{major}."):
            report.add(
                StoreCheckItem(
                    "version",
                    "Version format",
                    "warn",
                    f"Version {version} major does not match connection Odoo {major}",
                )
            )
        else:
            report.add(StoreCheckItem("version", "Version format", "pass", version))
    else:
        report.add(
            StoreCheckItem(
                "version",
                "Version format",
                "fail",
                "Version must match <major>.0.x.y.z (e.g. 19.0.1.0.0)",
            )
        )

    license_key = str(manifest.get("license") or "").strip()
    if license_key in VALID_LICENSES:
        report.add(StoreCheckItem("license", "License key", "pass", license_key))
    else:
        report.add(
            StoreCheckItem(
                "license",
                "License key",
                "fail",
                f"License {license_key!r} is not a known Apps license key",
            )
        )

    author = str(manifest.get("author") or "").strip()
    if author:
        report.add(StoreCheckItem("author", "Author", "pass", author[:80]))
    else:
        report.add(StoreCheckItem("author", "Author", "fail", "Manifest author is required"))

    website = str(manifest.get("website") or "").strip()
    if website.startswith("http"):
        report.add(StoreCheckItem("website", "Website", "pass", website[:120]))
    elif website:
        report.add(StoreCheckItem("website", "Website", "warn", "Website should be a full https:// URL"))
    else:
        report.add(StoreCheckItem("website", "Website", "warn", "Website URL recommended for Apps listing"))

    icon_path = f"{technical_name}/static/description/icon.png"
    if icon_path in zip_members:
        status: CheckStatus = "warn" if icon_is_placeholder else "pass"
        msg = "Placeholder icon included — replace before submission" if icon_is_placeholder else "icon.png present"
        report.add(StoreCheckItem("icon", "Module icon", status, msg))
    else:
        report.add(StoreCheckItem("icon", "Module icon", "fail", "Missing static/description/icon.png"))

    index_path = f"{technical_name}/static/description/index.html"
    if index_path in zip_members:
        report.add(StoreCheckItem("index_html", "Apps listing page", "pass", "index.html present"))
    else:
        report.add(
            StoreCheckItem(
                "index_html",
                "Apps listing page",
                "fail",
                "Missing static/description/index.html",
            )
        )

    return report.finalize()


def check_zip_store_readiness(
    zip_bytes: bytes,
    *,
    technical_name: str,
    major: int | None,
    icon_is_placeholder: bool = False,
) -> StoreReadinessReport:
    manifest = manifest_from_zip(zip_bytes, technical_name)
    members = zip_member_names(zip_bytes)
    return check_store_readiness(
        manifest=manifest,
        zip_members=members,
        technical_name=technical_name,
        major=major,
        icon_is_placeholder=icon_is_placeholder,
    )

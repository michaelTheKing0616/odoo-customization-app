"""Generate Expert vertical playbook chunks from catalog + domain packs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.expert.chunker import DocChunk, chunk_document, chunk_file
from app.expert.vertical_catalog import VERTICAL_CATALOG, VerticalEntry

_REPO_ROOT = Path(__file__).resolve().parents[4]
_VERTICALS_DIR = _REPO_ROOT / "docs" / "expert" / "verticals"


def vertical_doc_paths() -> list[Path]:
    if not _VERTICALS_DIR.is_dir():
        return []
    paths: list[Path] = []
    for path in sorted(_VERTICALS_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue
        paths.append(path)
    return paths


def _pack_factory(domain_pack_id: str):
    from app.ai_domain_packs import _PACK_FACTORIES

    for pack_id, factory, _ in _PACK_FACTORIES:
        if pack_id == domain_pack_id:
            return factory
    return None


def render_domain_pack_section(entry: VerticalEntry) -> str:
    """Markdown synopsis of a domain pack for Expert retrieval."""
    if not entry.domain_pack_id:
        return ""
    factory = _pack_factory(entry.domain_pack_id)
    if factory is None:
        return ""
    pack: dict[str, Any] = factory()
    lines = [
        f"## Domain pack scaffold: {pack.get('display_name') or entry.domain_pack_id}",
        "",
        f"Technical name: `{pack.get('technical_name') or entry.domain_pack_id}`.",
        f"Suggested depends: `{', '.join(pack.get('depends') or [])}`.",
        "",
        "Use **Draft Studio / App Wizard** in this app to scaffold these custom models, "
        "then sandbox-test before production.",
        "",
    ]
    models = pack.get("models") or []
    if models:
        lines.append("### Custom models in the pack")
        lines.append("")
        for model in models[:12]:
            if not isinstance(model, dict):
                continue
            name = model.get("model") or "x_model"
            desc = model.get("description") or ""
            fields = model.get("fields") or []
            field_names = [
                str(f.get("string") or f.get("name"))
                for f in fields[:8]
                if isinstance(f, dict)
            ]
            lines.append(f"- **{name}** — {desc}")
            if field_names:
                lines.append(f"  Fields: {', '.join(field_names)}.")
        if len(models) > 12:
            lines.append(f"- … and {len(models) - 12} more models in the full pack.")
        lines.append("")
    automations = pack.get("automations") or []
    if automations:
        lines.append("### Starter automations")
        lines.append("")
        for auto in automations[:5]:
            if isinstance(auto, dict):
                lines.append(f"- {auto.get('name')} on `{auto.get('model')}` ({auto.get('trigger')})")
        lines.append("")
    hints = pack.get("reuse_hints") or []
    if hints:
        lines.append("### Reuse stock Odoo models")
        lines.append("")
        for hint in hints[:6]:
            if isinstance(hint, dict):
                lines.append(f"- `{hint.get('model')}` — {hint.get('reason')}")
        lines.append("")
    return "\n".join(lines)


def render_catalog_playbook(entry: VerticalEntry) -> str:
    """Single vertical playbook document for chunking."""
    modules = ", ".join(f"`{m}`" for m in entry.stock_modules)
    keywords = ", ".join(entry.keywords)
    pack_section = render_domain_pack_section(entry)
    return f"""# Vertical playbook: {entry.title}

Expert vertical guidance for Odoo Community customization (public ORM/RPC only).
Vertical id: `{entry.id}`. Keywords: {keywords}.

## Summary

{entry.summary}

## Stock Odoo apps to install (typical order)

Install via Apps on your Odoo instance or include in generated module `depends`:

{modules}

Start with **Contacts**, **Mail**, and **Website** when you need portals or public forms.
Add **Sales** and **Accounting** when you invoice. Add **Inventory**, **Manufacturing**,
or **Project** only when the workflow truly needs them — fewer apps means simpler maintenance.

## Custom modules vs stock apps

Most verticals need **custom models** (`x_` prefix) for domain-specific records the stock apps
do not provide. Use this app's **Models & Fields** builder or **Draft Studio** domain packs.
Export an installable module and **sandbox-test** before production.

When a domain pack exists for this vertical (see below), prefer scaffolding from the pack
rather than inventing model names from scratch.

## Community vs Enterprise honesty

This guidance targets **Odoo Community** via public metadata APIs. Some Odoo marketing pages
describe Education, Sign, Documents, or Payroll features that are **Enterprise-only** or
Online-specific. If a feature is not in your installed module list, treat it as unavailable
and use the Community alternatives listed here or a custom `x_` model.

Never bypass protected tier-1 areas (accounting postings, payroll, payments) with ad-hoc code.

## Rollout phases

**Phase 1 — Foundation:** Contacts structure (tags/categories), core security groups, one
primary custom model, basic form/list views, menus.

**Phase 2 — Operations:** Automations (`base.automation`), scheduled actions, email templates,
portal/website pages where needed.

**Phase 3 — Scale:** Bulk import, reporting, optional module export for repeat deployments.

{pack_section}
## How to ask Expert follow-ups

Connect an Odoo instance so Expert can filter docs to your server version and list installed
modules. Ask specific questions: "Which stock modules for admissions?" or "Scaffold a student
model linked to Contacts."
"""


def _authored_vertical_ids() -> set[str]:
    return {p.stem.replace("-", "_") for p in vertical_doc_paths()}


def domain_pack_playbook_chunks() -> list[DocChunk]:
    """Chunks generated from domain-pack-linked catalog entries."""
    chunks: list[DocChunk] = []
    seen: set[str] = set()
    authored = _authored_vertical_ids()
    for entry in VERTICAL_CATALOG:
        if not entry.domain_pack_id or entry.domain_pack_id in seen:
            continue
        if entry.id in authored:
            continue
        seen.add(entry.domain_pack_id)
        md = render_catalog_playbook(entry)
        for chunk in chunk_document(md, source_path=f"vertical_{entry.id}.md", fmt="md"):
            chunks.append(chunk)
    return chunks


def catalog_playbook_chunks_without_pack_file() -> list[DocChunk]:
    """Catalog entries without a hand-authored markdown file or domain pack doc."""
    authored = _authored_vertical_ids()
    chunks: list[DocChunk] = []
    for entry in VERTICAL_CATALOG:
        if entry.id in authored or entry.domain_pack_id:
            continue
        md = render_catalog_playbook(entry)
        for chunk in chunk_document(md, source_path=f"vertical_{entry.id}.md", fmt="md"):
            chunks.append(chunk)
    return chunks


def all_vertical_playbook_chunks() -> list[DocChunk]:
    chunks: list[DocChunk] = []
    for path in vertical_doc_paths():
        chunks.extend(chunk_file(path))
    chunks.extend(domain_pack_playbook_chunks())
    chunks.extend(catalog_playbook_chunks_without_pack_file())
    return chunks


__all__ = [
    "all_vertical_playbook_chunks",
    "catalog_playbook_chunks_without_pack_file",
    "domain_pack_playbook_chunks",
    "render_catalog_playbook",
    "vertical_doc_paths",
]

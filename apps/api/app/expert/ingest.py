"""CLI and orchestration for Expert RAG knowledge-base ingestion."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.db import SessionLocal, init_db
from app.expert.chunker import chunk_file
from app.expert.fetcher import SUPPORTED_VERSIONS, fetch_documentation, iter_doc_files
from app.expert.store import UpsertStats, upsert_chunks
from app.expert.vertical_playbooks import all_vertical_playbook_chunks

from app.settings import settings

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass
class IngestReport:
    version: str
    odoo_docs: UpsertStats = field(default_factory=UpsertStats)
    project: UpsertStats = field(default_factory=UpsertStats)
    community: UpsertStats = field(default_factory=UpsertStats)
    vertical: UpsertStats = field(default_factory=UpsertStats)

    @property
    def total_inserted(self) -> int:
        return (
            self.odoo_docs.inserted
            + self.project.inserted
            + self.community.inserted
            + self.vertical.inserted
        )

    @property
    def total_updated(self) -> int:
        return (
            self.odoo_docs.updated
            + self.project.updated
            + self.community.updated
            + self.vertical.updated
        )


def _project_doc_paths() -> list[Path]:
    paths: list[Path] = []
    master = _REPO_ROOT / "docs" / "reference" / "MASTER_REFERENCE.md"
    if master.is_file():
        paths.append(master)
    docs_dir = _REPO_ROOT / "docs"
    if docs_dir.is_dir():
        for pattern in ("*.md",):
            for path in sorted(docs_dir.glob(pattern)):
                if path.name.startswith("."):
                    continue
                if path not in paths:
                    paths.append(path)
    return paths


def _community_doc_paths() -> list[Path]:
    mode = settings.expert_community_source.strip().lower()
    if mode != "dir":
        return []
    root = Path(settings.expert_community_dir.strip() or "")
    if not root.is_dir():
        logger.warning("EXPERT_COMMUNITY_DIR is not a directory: %s", root)
        return []
    files: list[Path] = []
    for pattern in ("**/*.md", "**/*.markdown", "**/*.rst"):
        files.extend(sorted(root.glob(pattern)))
    return files


def ingest_odoo_docs(version: str, *, offline: bool = False, embed: bool = True) -> UpsertStats:
    content_dir = fetch_documentation(version, offline=offline)
    stats = UpsertStats()
    db = SessionLocal()
    try:
        batch: list = []
        for path in iter_doc_files(content_dir):
            batch.extend(chunk_file(path))
            if len(batch) >= 200:
                part = upsert_chunks(db, source="odoo_docs", version=version, chunks=batch, embed=embed)
                stats.inserted += part.inserted
                stats.updated += part.updated
                stats.skipped += part.skipped
                batch = []
        if batch:
            part = upsert_chunks(db, source="odoo_docs", version=version, chunks=batch, embed=embed)
            stats.inserted += part.inserted
            stats.updated += part.updated
            stats.skipped += part.skipped
    finally:
        db.close()
    return stats


def ingest_project_docs(*, embed: bool = True) -> UpsertStats:
    paths = _project_doc_paths()
    if not paths:
        logger.info("No project docs found to ingest")
        return UpsertStats()
    db = SessionLocal()
    try:
        chunks = []
        for path in paths:
            chunks.extend(chunk_file(path))
        return upsert_chunks(db, source="project", version="all", chunks=chunks, embed=embed)
    finally:
        db.close()


def ingest_community_docs(*, embed: bool = True) -> UpsertStats:
    paths = _community_doc_paths()
    if not paths:
        return UpsertStats()
    db = SessionLocal()
    try:
        chunks = []
        for path in paths:
            chunks.extend(chunk_file(path))
        return upsert_chunks(db, source="community", version="all", chunks=chunks, embed=embed)
    finally:
        db.close()


def ingest_vertical_docs(*, embed: bool = True) -> UpsertStats:
    chunks = all_vertical_playbook_chunks()
    if not chunks:
        logger.info("No vertical playbook chunks to ingest")
        return UpsertStats()
    db = SessionLocal()
    try:
        return upsert_chunks(db, source="vertical", version="all", chunks=chunks, embed=embed)
    finally:
        db.close()


def run_ingest(
    version: str,
    *,
    offline: bool = False,
    skip_odoo_docs: bool = False,
    skip_project: bool = False,
    skip_community: bool = False,
    skip_vertical: bool = False,
    embed: bool = True,
) -> IngestReport:
    init_db()
    report = IngestReport(version=version)
    if skip_odoo_docs:
        report.odoo_docs = UpsertStats()
    else:
        report.odoo_docs = ingest_odoo_docs(version, offline=offline, embed=embed)
    if not skip_project:
        report.project = ingest_project_docs(embed=embed)
    if not skip_community:
        report.community = ingest_community_docs(embed=embed)
    if not skip_vertical:
        report.vertical = ingest_vertical_docs(embed=embed)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest Odoo Expert knowledge base")
    parser.add_argument(
        "--version",
        required=True,
        choices=list(SUPPORTED_VERSIONS),
        help="Odoo documentation branch to ingest",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use cached documentation only (no git fetch)",
    )
    parser.add_argument("--skip-project", action="store_true")
    parser.add_argument("--skip-community", action="store_true")
    parser.add_argument(
        "--skip-odoo-docs",
        action="store_true",
        help="Skip official Odoo documentation (re-index project/vertical only)",
    )
    parser.add_argument(
        "--skip-vertical",
        action="store_true",
        help="Skip vertical playbook ingest",
    )
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding generation")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    report = run_ingest(
        args.version,
        offline=args.offline,
        skip_odoo_docs=args.skip_odoo_docs,
        skip_project=args.skip_project,
        skip_community=args.skip_community,
        skip_vertical=args.skip_vertical,
        embed=not args.no_embed,
    )
    print(
        f"version={report.version} "
        f"odoo_docs=+{report.odoo_docs.inserted}/~{report.odoo_docs.updated} "
        f"project=+{report.project.inserted}/~{report.project.updated} "
        f"community=+{report.community.inserted}/~{report.community.updated} "
        f"vertical=+{report.vertical.inserted}/~{report.vertical.updated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Re-encrypt OdooConnection.secret_encrypted when rotating FERNET_KEY."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running from repo root via scripts/rotate_fernet_key.sh
API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from cryptography.fernet import Fernet, InvalidToken  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402


def _fernet(key: str) -> Fernet:
    raw = key.encode("utf-8")
    if key.startswith("dev-only-"):
        import base64
        import hashlib

        digest = hashlib.sha256(b"odoo-custom-local-dev-fernet-v1").digest()
        raw = base64.urlsafe_b64encode(digest)
    return Fernet(raw)


def rotate(*, old_key: str, new_key: str, dry_run: bool) -> int:
    old_f = _fernet(old_key)
    new_f = _fernet(new_key)
    init_db()
    db: Session = SessionLocal()
    rotated = 0
    failed = 0
    try:
        rows = db.query(OdooConnection).order_by(OdooConnection.created_at).all()
        for row in rows:
            try:
                plain = old_f.decrypt(row.secret_encrypted.encode("utf-8"))
            except InvalidToken:
                failed += 1
                print(f"SKIP {row.id} ({row.name}): cannot decrypt with OLD_FERNET_KEY", file=sys.stderr)
                continue
            if dry_run:
                rotated += 1
                continue
            row.secret_encrypted = new_f.encrypt(plain).decode("utf-8")
            db.add(row)
            rotated += 1
        if not dry_run:
            db.commit()
    finally:
        db.close()
    mode = "would rotate" if dry_run else "rotated"
    print(f"{mode} {rotated} connection secret(s); {failed} decrypt failure(s)")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate Fernet-encrypted Odoo credentials")
    parser.add_argument("--dry-run", action="store_true", help="Count rows without writing")
    args = parser.parse_args()
    old_key = os.environ.get("OLD_FERNET_KEY", "").strip()
    new_key = os.environ.get("NEW_FERNET_KEY", "").strip()
    if not old_key or not new_key:
        print("Set OLD_FERNET_KEY and NEW_FERNET_KEY in the environment.", file=sys.stderr)
        return 2
    if old_key == new_key:
        print("OLD_FERNET_KEY and NEW_FERNET_KEY must differ.", file=sys.stderr)
        return 2
    return rotate(old_key=old_key, new_key=new_key, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

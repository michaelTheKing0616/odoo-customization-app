#!/usr/bin/env python3
"""Generate APP_ADMIN_PASSWORD and append to local .env (MON-3). Never commit output."""

from __future__ import annotations

import secrets
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"


def main() -> None:
    password = secrets.token_urlsafe(24)
    email = "admin@localhost"
    lines = [
        "",
        "# MON-3 bootstrap — generated once; change after first login",
        f"APP_ADMIN_EMAIL={email}",
        f"APP_ADMIN_PASSWORD={password}",
        "AUTH_MODE=accounts",
    ]
    existing = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    if "APP_ADMIN_PASSWORD=" in existing:
        print("APP_ADMIN_PASSWORD already set in .env — not overwriting.")
        print(f"Edit {ENV_PATH} manually if you need a new password.")
        return
    with ENV_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote admin credentials to {ENV_PATH}")
    print("Email:", email)
    print("Password: (see .env — not repeated here)")
    print("Change the password after first login.")


if __name__ == "__main__":
    main()

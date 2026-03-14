"""Configuration loaded from environment variables."""

import os
from typing import Set


def _parse_admin_ids(raw: str) -> Set[int]:
    """Parse a comma-separated string of integers into a set."""
    ids: Set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                ids.add(int(part))
            except ValueError:
                pass
    return ids


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: Set[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
DB_PATH: str = os.getenv("DB_PATH", "bot_users.db")

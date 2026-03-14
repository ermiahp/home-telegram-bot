"""SQLite-backed users database.

Schema
------
users(
    user_id   INTEGER PRIMARY KEY,
    username  TEXT,
    full_name TEXT,
    status    TEXT  -- 'pending' | 'approved' | 'denied'
)
"""

import sqlite3
from contextlib import contextmanager
from typing import Generator, List, Optional, Tuple

# Status constants
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DENIED = "denied"


class Database:
    """Manages a SQLite database of bot users."""

    def __init__(self, db_path: str = "bot_users.db") -> None:
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create the users table if it does not exist."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id   INTEGER PRIMARY KEY,
                    username  TEXT,
                    full_name TEXT,
                    status    TEXT NOT NULL DEFAULT 'pending'
                )
                """
            )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_user(
        self,
        user_id: int,
        username: Optional[str],
        full_name: str,
    ) -> bool:
        """Insert a new user with *pending* status.

        Returns True if a new row was inserted, False if the user already
        existed (no update is performed so as not to reset the status).
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO users (user_id, username, full_name, status)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, username, full_name, STATUS_PENDING),
            )
            return cursor.rowcount > 0

    def set_status(self, user_id: int, status: str) -> bool:
        """Update *status* for the given *user_id*.

        Returns True if a row was actually updated.
        """
        if status not in (STATUS_PENDING, STATUS_APPROVED, STATUS_DENIED):
            raise ValueError(f"Invalid status: {status!r}")
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE users SET status = ? WHERE user_id = ?",
                (status, user_id),
            )
            return cursor.rowcount > 0

    def approve_user(self, user_id: int) -> bool:
        """Approve a user. Returns True on success."""
        return self.set_status(user_id, STATUS_APPROVED)

    def deny_user(self, user_id: int) -> bool:
        """Deny a user. Returns True on success."""
        return self.set_status(user_id, STATUS_DENIED)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_user(self, user_id: int) -> Optional[sqlite3.Row]:
        """Return a single user row or None."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            return cursor.fetchone()

    def is_approved(self, user_id: int) -> bool:
        """Return True if the user exists and is approved."""
        row = self.get_user(user_id)
        return row is not None and row["status"] == STATUS_APPROVED

    def list_users(
        self, status: Optional[str] = None
    ) -> List[sqlite3.Row]:
        """Return all users, optionally filtered by *status*."""
        with self._connect() as conn:
            if status is None:
                cursor = conn.execute("SELECT * FROM users ORDER BY user_id")
            else:
                cursor = conn.execute(
                    "SELECT * FROM users WHERE status = ? ORDER BY user_id",
                    (status,),
                )
            return cursor.fetchall()

    def list_pending(self) -> List[sqlite3.Row]:
        """Convenience: return all pending users."""
        return self.list_users(STATUS_PENDING)

    def count_by_status(self) -> Tuple[int, int, int]:
        """Return (pending_count, approved_count, denied_count)."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM users
                GROUP BY status
                """
            )
            rows = {r["status"]: r["cnt"] for r in cursor.fetchall()}
        return (
            rows.get(STATUS_PENDING, 0),
            rows.get(STATUS_APPROVED, 0),
            rows.get(STATUS_DENIED, 0),
        )

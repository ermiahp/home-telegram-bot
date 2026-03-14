"""Unit tests for bot/database.py."""

import os
import tempfile

import pytest

from bot.database import (
    Database,
    STATUS_APPROVED,
    STATUS_DENIED,
    STATUS_PENDING,
)


@pytest.fixture
def db():
    """Provide a fresh temporary Database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    database = Database(db_path=path)
    yield database
    os.unlink(path)


# ---------------------------------------------------------------------------
# add_user
# ---------------------------------------------------------------------------


def test_add_user_inserts_new_user(db):
    inserted = db.add_user(user_id=1, username="alice", full_name="Alice A")
    assert inserted is True
    row = db.get_user(1)
    assert row is not None
    assert row["user_id"] == 1
    assert row["username"] == "alice"
    assert row["full_name"] == "Alice A"
    assert row["status"] == STATUS_PENDING


def test_add_user_duplicate_returns_false(db):
    db.add_user(user_id=2, username="bob", full_name="Bob B")
    inserted = db.add_user(user_id=2, username="bob", full_name="Bob B")
    assert inserted is False


def test_add_user_duplicate_does_not_reset_status(db):
    db.add_user(user_id=3, username="carol", full_name="Carol C")
    db.approve_user(3)
    db.add_user(user_id=3, username="carol", full_name="Carol C")  # duplicate
    assert db.get_user(3)["status"] == STATUS_APPROVED


def test_add_user_without_username(db):
    inserted = db.add_user(user_id=10, username=None, full_name="NoUser")
    assert inserted is True
    assert db.get_user(10)["username"] is None


# ---------------------------------------------------------------------------
# approve_user / deny_user
# ---------------------------------------------------------------------------


def test_approve_user(db):
    db.add_user(user_id=4, username="dave", full_name="Dave D")
    result = db.approve_user(4)
    assert result is True
    assert db.get_user(4)["status"] == STATUS_APPROVED


def test_deny_user(db):
    db.add_user(user_id=5, username="eve", full_name="Eve E")
    result = db.deny_user(5)
    assert result is True
    assert db.get_user(5)["status"] == STATUS_DENIED


def test_approve_nonexistent_user_returns_false(db):
    result = db.approve_user(999)
    assert result is False


def test_deny_nonexistent_user_returns_false(db):
    result = db.deny_user(999)
    assert result is False


# ---------------------------------------------------------------------------
# is_approved
# ---------------------------------------------------------------------------


def test_is_approved_returns_false_for_pending(db):
    db.add_user(user_id=6, username="frank", full_name="Frank F")
    assert db.is_approved(6) is False


def test_is_approved_returns_true_after_approve(db):
    db.add_user(user_id=7, username="grace", full_name="Grace G")
    db.approve_user(7)
    assert db.is_approved(7) is True


def test_is_approved_returns_false_for_unknown_user(db):
    assert db.is_approved(9999) is False


# ---------------------------------------------------------------------------
# list_users
# ---------------------------------------------------------------------------


def test_list_users_returns_all(db):
    db.add_user(1, "u1", "User One")
    db.add_user(2, "u2", "User Two")
    db.add_user(3, "u3", "User Three")
    rows = db.list_users()
    assert len(rows) == 3


def test_list_users_filtered_by_status(db):
    db.add_user(1, "u1", "User One")
    db.add_user(2, "u2", "User Two")
    db.approve_user(1)
    approved = db.list_users(STATUS_APPROVED)
    assert len(approved) == 1
    assert approved[0]["user_id"] == 1


def test_list_pending_returns_only_pending(db):
    db.add_user(1, "u1", "User One")
    db.add_user(2, "u2", "User Two")
    db.approve_user(2)
    pending = db.list_pending()
    assert len(pending) == 1
    assert pending[0]["user_id"] == 1


# ---------------------------------------------------------------------------
# count_by_status
# ---------------------------------------------------------------------------


def test_count_by_status(db):
    db.add_user(1, "u1", "User One")
    db.add_user(2, "u2", "User Two")
    db.add_user(3, "u3", "User Three")
    db.approve_user(1)
    db.deny_user(2)
    pending, approved, denied = db.count_by_status()
    assert pending == 1
    assert approved == 1
    assert denied == 1


def test_count_by_status_empty_db(db):
    pending, approved, denied = db.count_by_status()
    assert pending == 0
    assert approved == 0
    assert denied == 0


# ---------------------------------------------------------------------------
# set_status validation
# ---------------------------------------------------------------------------


def test_set_status_invalid_raises_value_error(db):
    db.add_user(1, "u1", "User One")
    with pytest.raises(ValueError, match="Invalid status"):
        db.set_status(1, "banned")

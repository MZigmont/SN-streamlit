"""Persist the last synchronized contents separately from each local database."""

import hashlib
from pathlib import Path


def fingerprint(db_path):
    digest = hashlib.sha256()
    with open(db_path, "rb") as database:
        for chunk in iter(lambda: database.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def state_path(db_path):
    return Path(str(db_path) + ".sync-sha256")


def mark_synced(db_path, digest=None):
    state_path(db_path).write_text(digest or fingerprint(db_path), encoding="ascii")


def has_unsynced_changes(db_path):
    baseline = state_path(db_path)
    return not baseline.exists() or baseline.read_text(encoding="ascii") != fingerprint(db_path)

"""Private, SQLite-consistent ACTCalc backups and non-destructive restores.

Backups contain visitor contact messages and MUST remain in restricted storage.
Restore produces a NEW database file; the operator swaps the configured path
only after shutting down the old instance and checking the restored copy.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import sqlite3

REQUIRED_COLUMNS={'id','received','name','email','topic','body','token_hash','ip_hash','mail_status','mail_attempts'}


def _verify_sqlite(path:Path)->int:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError('Backup file is missing or empty.')
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=15)
    try:
        result=db.execute('PRAGMA integrity_check').fetchone()
        if result != ('ok',):
            raise ValueError('SQLite integrity check failed.')
        cols={x[1] for x in db.execute('PRAGMA table_info(contacts)')}
        if not REQUIRED_COLUMNS <= cols:
            raise ValueError('This is not an ACTCalc contact database.')
        return int(db.execute('SELECT COUNT(*) FROM contacts').fetchone()[0])
    finally:
        db.close()


def _snapshot(source:Path,destination:Path)->int:
    if not source.is_file():
        raise FileNotFoundError('Source database is missing.')
    if destination.exists():
        raise FileExistsError('Refusing to overwrite an existing file.')
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if destination.parent.resolve().is_relative_to(Path(__file__).resolve().parents[1]/'static'):
        raise ValueError('Backups cannot be stored inside public static assets.')
    temp=destination.with_name('.'+destination.name+'.partial-'+secrets.token_hex(5))
    try:
        with sqlite3.connect(source,timeout=20) as src:
            with sqlite3.connect(temp,timeout=20) as dst:
                src.backup(dst,pages=32,sleep=0.1)
        os.chmod(temp,0o600)
        count=_verify_sqlite(temp)
        # Refuse races or accidental overwrite instead of replacing a backup.
        os.link(temp,destination)
        os.unlink(temp)
        return count
    finally:
        if temp.exists():temp.unlink()


def backup(source:Path,destination:Path)->int:
    """Create a consistent private backup while the application is running."""
    return _snapshot(source,destination)


def restore_as_new(archive:Path,new_database:Path)->int:
    """Restore to a *new* file; never overwrite an active SQLite database."""
    _verify_sqlite(archive)
    if new_database.resolve()==archive.resolve():
        raise ValueError('Choose a distinct target database path.')
    return _snapshot(archive,new_database)


def verify(path:Path)->int:
    return _verify_sqlite(path)

from __future__ import annotations
import os
from pathlib import Path
import sqlite3
import pytest
from backend import db,backup


def test_live_snapshot_restore_non_destructive(tmp_path):
    original=tmp_path/'actcalc.sqlite3'
    db.initialize(original)
    item={'name':'Audit','email':'a@example.org','topic':'Question','message':'This is a genuine submitted contact enquiry.'}
    assert db.insert(original,item,'random_one','iphash')[0]
    copy=tmp_path/'private'/'backups'/'first.sqlite3'
    assert backup.backup(original,copy)==1
    assert backup.verify(copy)==1
    assert os.stat(copy).st_mode & 0o777 == 0o600
    assert db.insert(original,item,'random_two','iphash')[0]
    dest=tmp_path/'restored.sqlite3'
    assert backup.restore_as_new(copy,dest)==1
    assert backup.verify(dest)==1
    assert len(db.list_contacts(dest))==1
    assert len(db.list_contacts(original))==2
    with pytest.raises(FileExistsError):backup.restore_as_new(copy,dest)
    with pytest.raises(FileExistsError):backup.backup(original,copy)


def test_corrupt_or_wrong_backup_is_rejected(tmp_path):
    junk=tmp_path/'file.sqlite3'
    junk.write_bytes(b'not a database')
    with pytest.raises((sqlite3.DatabaseError,ValueError)):
        backup.restore_as_new(junk,tmp_path/'restore.sqlite3')
    unrelated=tmp_path/'different.sqlite3'
    with sqlite3.connect(unrelated) as con: con.execute('CREATE TABLE different(x INTEGER)')
    with pytest.raises(ValueError):backup.verify(unrelated)
    assert not (tmp_path/'restore.sqlite3').exists()


def test_snapshot_during_wal_reader(tmp_path):
    original=tmp_path/'active.sqlite3'
    db.initialize(original)
    with sqlite3.connect(original) as reader:
        reader.execute('PRAGMA journal_mode=WAL')
        reader.execute('BEGIN')
        reader.execute('SELECT * FROM contacts').fetchall()
        item={'name':'Audit','email':'a@example.org','topic':'Question','message':'This is a genuine submitted contact enquiry.'}
        assert db.insert(original,item,'wal_item','iphash')[0]
        copy=tmp_path/'wal-copy.sqlite3'
        assert backup.backup(original,copy)==1
        assert backup.verify(copy)==1

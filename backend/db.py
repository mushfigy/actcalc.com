from __future__ import annotations
import sqlite3, time
from pathlib import Path
from contextlib import contextmanager

CREATE='''
CREATE TABLE IF NOT EXISTS contacts(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 received INTEGER NOT NULL,
 name TEXT NOT NULL,
 email TEXT NOT NULL,
 topic TEXT NOT NULL,
 body TEXT NOT NULL,
 token_hash TEXT UNIQUE NOT NULL,
 ip_hash TEXT NOT NULL,
 mail_status TEXT NOT NULL DEFAULT 'pending',
 mail_attempts INTEGER NOT NULL DEFAULT 0,
 next_attempt INTEGER NOT NULL DEFAULT 0,
 last_error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_contacts_received ON contacts(received);
CREATE INDEX IF NOT EXISTS idx_contacts_ip_received ON contacts(ip_hash,received);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(mail_status,received);
'''

def initialize(path:Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with connection(path) as db:
        db.executescript(CREATE)
        # Existing operator databases from earlier releases are migrated in place.
        columns={r[1] for r in db.execute('PRAGMA table_info(contacts)')}
        if 'next_attempt' not in columns:
            db.execute('ALTER TABLE contacts ADD COLUMN next_attempt INTEGER NOT NULL DEFAULT 0')

@contextmanager
def connection(path:Path):
    con=sqlite3.connect(path,timeout=8, isolation_level=None)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA busy_timeout=8000')
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=NORMAL')
    try: yield con
    finally: con.close()

def purge(path:Path, days:int=30)->int:
    with connection(path) as con:
        x=con.execute('DELETE FROM contacts WHERE received < ?',(int(time.time())-days*86400,))
        return x.rowcount

def rate_count(con,ip_hash:str, seconds:int)->int:
    return con.execute('SELECT count(*) AS n FROM contacts WHERE ip_hash=? AND received>=?',(ip_hash,int(time.time())-seconds)).fetchone()['n']

def insert(path:Path,values:dict,token_hash:str,ip_hash:str)->tuple[bool,str]:
    with connection(path) as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            if rate_count(con,ip_hash,900)>=5 or rate_count(con,ip_hash,86400)>=25:
                con.execute('ROLLBACK');return False,'Too many submissions. Please try later.'
            con.execute('INSERT INTO contacts(received,name,email,topic,body,token_hash,ip_hash) VALUES(?,?,?,?,?,?,?)',(
                int(time.time()),values['name'],values['email'],values['topic'],values['message'],token_hash,ip_hash))
            con.execute('COMMIT')
            return True,'ok'
        except sqlite3.IntegrityError:
            con.execute('ROLLBACK');return False,'This form has already been submitted. Reopen Contact to try again.'
        except Exception:
            con.execute('ROLLBACK');raise

def list_contacts(path:Path,limit:int=30)->list[dict]:
    with connection(path) as con:
        return [dict(x) for x in con.execute('SELECT id,received,name,email,topic,body,mail_status,mail_attempts,next_attempt FROM contacts ORDER BY received DESC,id DESC LIMIT ?',(min(max(1,limit),100),)).fetchall()]

def pending(path:Path,limit:int=15)->list[dict]:
    with connection(path) as con:
        return [dict(x) for x in con.execute("SELECT id,received,name,email,topic,body,mail_attempts FROM contacts WHERE mail_status='pending' AND mail_attempts < 10 AND next_attempt<=? ORDER BY id ASC LIMIT ?",(int(time.time()),min(max(1,limit),50))).fetchall()]

def mark(path:Path,id:int,status:str):
    with connection(path) as con:
        row=con.execute('SELECT mail_attempts FROM contacts WHERE id=?',(id,)).fetchone()
        if row is None:return
        attempts=row['mail_attempts']+1
        if status=='sent':
            con.execute("UPDATE contacts SET mail_status='sent',mail_attempts=?,next_attempt=0,last_error='' WHERE id=?",(attempts,id))
        else:
            next_time=int(time.time())+min(60*(2**min(attempts-1,8)),14400)
            final='failed' if attempts>=10 else 'pending'
            con.execute('UPDATE contacts SET mail_status=?,mail_attempts=?,next_attempt=?,last_error=? WHERE id=?',(final,attempts,next_time,'Delivery failed; inspect server mail settings.',id))

def delete(path:Path,id:int):
    with connection(path) as con:
        return con.execute('DELETE FROM contacts WHERE id=?',(id,)).rowcount

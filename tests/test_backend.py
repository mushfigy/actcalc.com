from __future__ import annotations
from pathlib import Path
import hashlib, hmac, json, secrets, sqlite3, time
from dataclasses import replace
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app,script_csp, INDEX
from backend.config import Settings
from backend import db,mailer


@pytest.fixture
def setup_app(tmp_path):
    cfg=Settings(
        public=False,local_dev=True,operator_name='',privacy_email='',contact_secret='a'*48,
        admin_token='b'*48,db_path=tmp_path/'actcalc.sqlite3',smtp_host='',smtp_port=587,
        smtp_user='',smtp_password='',smtp_sender='',smtp_recipient='',allowed_hosts=('actcalc.com','www.actcalc.com'),smtp_mode='starttls')
    app=create_app(cfg)
    with TestClient(app,client=('127.0.0.1',45678)) as client:
        yield client,cfg

def send(client,token,**extra):
    data={'nonce':token,'email':'client@example.org','name':'Test User','topic':'Question','message':'Please clarify the pump calculation.','website':''}
    data.update(extra)
    return client.post('/api/contact',headers={'Origin':'http://testserver'},json=data)

def challenge(client):
    r=client.get('/api/contact');assert r.status_code==200 and r.json()['ready']
    return r.json()['nonce']

def test_fail_closed_default(tmp_path):
    c=Settings(public=True,local_dev=False,operator_name='',privacy_email='',contact_secret='',admin_token='',db_path=tmp_path/'data.sqlite3',smtp_host='',smtp_port=587,smtp_user='',smtp_password='',smtp_sender='',smtp_recipient='',allowed_hosts=('actcalc.com','www.actcalc.com'),smtp_mode='starttls')
    assert not c.ready
    with TestClient(create_app(c),client=('198.51.100.3',51352),base_url='https://actcalc.com') as client:
        assert client.get('/').status_code==503
        assert client.get('/api/health').json()['public_access_enabled'] is False
        assert 'Disallow' not in client.get('/robots.txt').text # access denied

def test_local_only_and_security_headers(setup_app):
    client,cfg=setup_app
    html=client.get('/')
    assert html.status_code==200
    assert 'ACTOfflineReview=(location.protocol===' in html.text
    assert '/api/contact' in html.text
    assert 'Content-Security-Policy' in html.headers
    assert "script-src 'self' 'sha256-" in html.headers['Content-Security-Policy']
    assert "script-src 'self' 'unsafe-inline'" not in html.headers['Content-Security-Policy']
    assert html.headers['x-frame-options']=='DENY'
    assert client.get('/privacy').status_code==200
    assert client.get('/terms').status_code==200
    assert client.get('/icons/actcalc-192.png').status_code==200
    assert client.get('/manifest.webmanifest').status_code==200
    assert client.get('/sw.js').status_code==200
    assert 'Disallow: /' in client.get('/robots.txt').text
    assert client.get('/api/health').json()['public_release_configuration_ready'] is False

def test_contact_happy_path_and_replay(setup_app):
    client,cfg=setup_app
    token=challenge(client)
    ok=send(client,token)
    assert ok.status_code==200 and ok.json()['accepted']
    assert 'queued' in ok.json()['message']
    re=send(client,token)
    assert re.status_code==429 and not re.json()['accepted']
    assert len(db.list_contacts(cfg.db_path))==1

def test_validation_and_replay_rejection(setup_app):
    client,cfg=setup_app
    assert send(client,'invalid').status_code==403
    tok=challenge(client)
    assert send(client,tok,email='invalid').status_code==422
    assert send(client,tok,topic='bad').status_code==422
    assert send(client,tok,message='short').status_code==422
    assert send(client,tok,website='bogus.com').status_code==200
    assert not db.list_contacts(cfg.db_path)
    assert send(client,tok,email='client@example.org',message='OK I have a valid long message').status_code==200 # Honeypot does not consume token

def test_csrf_rejected(setup_app):
    client,cfg=setup_app
    token=challenge(client)
    r=client.post('/api/contact',headers={'Origin':'https://evil.example'},json={'nonce':token,'email':'client@example.org','topic':'Question','message':'12345678901'})
    assert r.status_code==403
    r=client.post('/api/contact',json={'nonce':token,'email':'client@example.org','topic':'Question','message':'12345678901'})
    assert r.status_code==403

def test_rate_limit_per_connection(setup_app):
    client,cfg=setup_app
    for i in range(5):
        assert send(client,challenge(client)).status_code==200
    assert send(client,challenge(client)).status_code==429

def test_admin_access_and_purge(setup_app):
    client,cfg=setup_app
    assert send(client,challenge(client)).status_code==200
    assert client.get('/api/admin/messages').status_code==401
    assert client.get('/api/admin/messages',headers={'Authorization':'Bearer '+'x'*48}).status_code==401
    r=client.get('/api/admin/messages',headers={'Authorization':'Bearer '+cfg.admin_token})
    assert len(r.json()['messages'])==1
    id=r.json()['messages'][0]['id']
    assert client.delete(f'/api/admin/messages/{id}',headers={'Authorization':'Bearer '+cfg.admin_token}).json()['deleted']
    assert not db.list_contacts(cfg.db_path)
    assert send(client,challenge(client)).status_code==200
    with db.connection(cfg.db_path) as con:con.execute('UPDATE contacts SET received=?',(int(time.time())-31*86400,))
    assert db.purge(cfg.db_path)==1

def test_mailer_success_and_retry(setup_app):
    client,cfg=setup_app
    assert send(client,challenge(client)).status_code==200
    configured=replace(cfg,smtp_host='smtp.example.com',smtp_user='me',smtp_password='pw',smtp_sender='sender@example.org',smtp_recipient='operator@example.org')
    with patch('backend.mailer.deliver_one',side_effect=RuntimeError('simulated')) as fake:
        assert mailer.send_batch(configured)['failed']==1
    # Retry is delayed; the outbox will not hammer an unavailable mail host.
    assert not db.pending(cfg.db_path)
    with db.connection(cfg.db_path) as con:con.execute('UPDATE contacts SET next_attempt=0')
    with patch('backend.mailer.deliver_one',return_value=None):
        assert mailer.send_batch(configured)['sent']==1
    assert db.list_contacts(cfg.db_path)[0]['mail_status']=='sent'

def test_complete_release_config(tmp_path):
    cfg=Settings(public=True,local_dev=False,operator_name='Verified legal operator',privacy_email='privacy@example.org',contact_secret='x'*48,admin_token='y'*48,db_path=Path('/data/actcalc.sqlite3'),smtp_host='smtp.example.org',smtp_port=587,smtp_user='user',smtp_password='password',smtp_sender='a@example.org',smtp_recipient='b@example.org',allowed_hosts=('actcalc.com','www.actcalc.com'),smtp_mode='starttls',legal_review_confirmed=True,smtp_delivery_verified=True,backup_restore_verified=True,live_device_verified=True)
    assert cfg.ready
    assert cfg.errors()==[]
    assert not replace(cfg,legal_review_confirmed=False).ready
    assert not replace(cfg,smtp_delivery_verified=False).ready
    assert not replace(cfg,smtp_password='').ready
    assert not replace(cfg,contact_secret='short').ready
    assert not replace(cfg,db_path=Path('/tmp/db.sqlite3')).ready

def test_safe_legal_and_no_unreviewed_price(setup_app):
    client,cfg=setup_app
    assert 'EUR 2,000' not in client.get('/').text
    assert 'Resend to deliver' not in client.get('/').text
    assert 'Privacy' in client.get('/').text
    assert '[Operator identity pending]' in client.get('/privacy').text # must not invent identity


def test_outbox_delays_failures_and_surfaces_terminal_failure(setup_app):
    client,cfg=setup_app
    assert send(client,challenge(client)).status_code==200
    message_id=db.list_contacts(cfg.db_path)[0]['id']
    for i in range(10):
        db.mark(cfg.db_path,message_id,'pending')
        if i<9:
            assert len(db.pending(cfg.db_path))==0
            with db.connection(cfg.db_path) as con:
                con.execute('UPDATE contacts SET next_attempt=0 WHERE id=?',(message_id,))
    item=db.list_contacts(cfg.db_path)[0]
    assert item['mail_status']=='failed' and item['mail_attempts']==10
    assert db.pending(cfg.db_path)==[]


def test_old_database_migrates_outbox_schema(tmp_path):
    file=tmp_path/'old.sqlite3'
    import sqlite3
    with sqlite3.connect(file) as con:
        con.execute('CREATE TABLE contacts(id INTEGER PRIMARY KEY AUTOINCREMENT,received INTEGER NOT NULL,name TEXT NOT NULL,email TEXT NOT NULL,topic TEXT NOT NULL,body TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,ip_hash TEXT NOT NULL,mail_status TEXT NOT NULL DEFAULT \"pending\",mail_attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT \"\")')
    db.initialize(file)
    with db.connection(file) as con:
        assert 'next_attempt' in {c[1] for c in con.execute('PRAGMA table_info(contacts)')}


def test_prod_like_public_routes_and_restart_persistence(prod_db_path):
    # Synthetic credentials are ONLY for local tests. No claim of SMTP/owner approval.
    cfg=Settings(public=True,local_dev=False,operator_name='TEST LEGAL OPERATOR',privacy_email='privacy@example.org',contact_secret='production-test-csrf-secret-'+'x'*42,admin_token='production-test-admin-secret-'+'y'*42,db_path=prod_db_path,smtp_host='smtp.invalid',smtp_port=587,smtp_user='test',smtp_password='test',smtp_sender='sender@example.org',smtp_recipient='operator@example.org',allowed_hosts=('actcalc.com','www.actcalc.com'),smtp_mode='starttls',legal_review_confirmed=True,smtp_delivery_verified=True,backup_restore_verified=True,live_device_verified=True)
    assert cfg.ready
    with TestClient(create_app(cfg),base_url='https://actcalc.com',client=('198.51.100.17',443)) as client:
        home=client.get('/')
        assert home.status_code==200
        assert 'rev3-production-candidate' in home.text
        assert 'Strict-Transport-Security' in home.headers
        assert '<link rel="canonical" href="https://actcalc.com/">' in home.text
        assert 'https://actcalc.com/icons/actcalc-512.png' in home.text
        assert client.get('/api/health').json()['public_access_enabled'] is True
        assert client.get('/icons/actcalc-512.png').status_code==200
        assert 'Disallow' not in client.get('/robots.txt').text
        token=client.get('/api/contact').json()['nonce']
        response=client.post('/api/contact',headers={'Origin':'https://actcalc.com'},json={'nonce':token,'email':'test@example.org','name':'Test','topic':'Feedback','message':'This is an integration test message.'})
        assert response.status_code==200 and response.json()['accepted']
        assert client.get('/api/admin/messages').status_code==401
    with TestClient(create_app(cfg),base_url='https://actcalc.com',client=('198.51.100.17',443)) as client:
        messages=client.get('/api/admin/messages',headers={'Authorization':'Bearer '+cfg.admin_token}).json()['messages']
        assert len(messages)==1 and messages[0]['topic']=='Feedback'
        assert messages[0]['mail_status']=='pending'
    with TestClient(create_app(cfg),base_url='https://www.actcalc.com',client=('198.51.100.88',443)) as client:
        token=client.get('/api/contact').json()['nonce']
        response=client.post('/api/contact',headers={'Origin':'https://www.actcalc.com'},json={'nonce':token,'email':'test2@example.org','topic':'Question','message':'This is another independent visitor.'})
        assert response.status_code==200
    assert len(db.list_contacts(cfg.db_path))==2


def test_fail_closed_flag_not_bypassed_by_public_switch(prod_db_path):
    cfg=Settings(public=True,local_dev=False,operator_name='TEST OPERATOR',privacy_email='privacy@example.org',contact_secret='x'*48,admin_token='y'*48,db_path=prod_db_path,smtp_host='smtp.invalid',smtp_port=587,smtp_user='test',smtp_password='test',smtp_sender='sender@example.org',smtp_recipient='operator@example.org',allowed_hosts=('actcalc.com','www.actcalc.com'),smtp_mode='starttls',legal_review_confirmed=False,smtp_delivery_verified=True,backup_restore_verified=True,live_device_verified=True)
    assert not cfg.ready
    with TestClient(create_app(cfg),base_url='https://actcalc.com',client=('198.51.100.4',443)) as client:
        assert client.get('/').status_code==503
        assert client.get('/api/health').json()['public_access_enabled'] is False


@pytest.fixture
def prod_db_path():
    # Simulate the host-mounted application storage at a path outside ephemeral
    # /tmp, without modifying production files or reducing Settings checks.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='actcalc-test-',dir=Path.home()) as folder:
        yield Path(folder)/'contacts.sqlite3'


def test_private_preview_restricted_but_operable(tmp_path):
    import base64
    cfg=Settings(public=False,local_dev=False,operator_name='',privacy_email='',contact_secret='a'*48,admin_token='b'*48,db_path=tmp_path/'contacts.sqlite3',smtp_host='',smtp_port=587,smtp_user='',smtp_password='',smtp_sender='',smtp_recipient='',allowed_hosts=('actcalc.com','www.actcalc.com'),smtp_mode='starttls',preview_token='p'*48)
    assert not cfg.ready
    from fastapi.testclient import TestClient
    with TestClient(create_app(cfg),base_url='https://actcalc.com',client=('198.51.100.70',443)) as client:
        denied=client.get('/')
        assert denied.status_code==401 and 'Basic' in denied.headers.get('www-authenticate','')
        assert client.get('/',headers={'Authorization':'Basic bm90OnRva2Vu'}).status_code==401
        encoded=base64.b64encode(('preview:'+cfg.preview_token).encode()).decode()
        head={'Authorization':'Basic '+encoded}
        assert client.get('/',headers=head).status_code==200
        assert client.get('/api/health').json()['public_access_enabled'] is False
        token=client.get('/api/contact',headers=head).json()['nonce']
        response=client.post('/api/contact',headers={**head,'Origin':'https://actcalc.com'},json={'nonce':token,'email':'preview@example.org','topic':'Question','message':'Private preview form end-to-end test.'})
        assert response.status_code==200 and response.json()['accepted']
        assert len(db.list_contacts(cfg.db_path))==1
    assert not cfg.ready

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


def truthy(v: str) -> bool:
    return v.strip().lower() in ('true', 'yes', '1', 'on')

@dataclass(frozen=True)
class Settings:
    public: bool
    local_dev: bool
    operator_name: str
    privacy_email: str
    contact_secret: str
    admin_token: str
    db_path: Path
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_sender: str
    smtp_recipient: str
    allowed_hosts: tuple[str, ...]
    smtp_mode: str
    preview_token: str = ''
    legal_review_confirmed: bool = False
    smtp_delivery_verified: bool = False
    backup_restore_verified: bool = False
    live_device_verified: bool = False

    @classmethod
    def from_env(cls) -> 'Settings':
        e=os.environ
        return cls(
            public=truthy(e.get('ACTCALC_PUBLIC','false')),
            local_dev=truthy(e.get('ACTCALC_ALLOW_LOCAL_DEV','false')),
            operator_name=e.get('ACTCALC_OPERATOR_NAME','').strip(),
            privacy_email=e.get('ACTCALC_PRIVACY_EMAIL','').strip(),
            contact_secret=e.get('ACTCALC_CONTACT_SECRET',''),
            admin_token=e.get('ACTCALC_ADMIN_TOKEN',''),
            db_path=Path(e.get('ACTCALC_DB_PATH','/data/actcalc.sqlite3')).expanduser(),
            smtp_host=e.get('ACTCALC_SMTP_HOST','').strip(),
            smtp_port=int(e.get('ACTCALC_SMTP_PORT','587')),
            smtp_user=e.get('ACTCALC_SMTP_USER','').strip(),
            smtp_password=e.get('ACTCALC_SMTP_PASSWORD',''),
            smtp_sender=e.get('ACTCALC_SMTP_SENDER','').strip(),
            smtp_recipient=e.get('ACTCALC_SMTP_RECIPIENT','').strip(),
            allowed_hosts=tuple(h.strip().lower() for h in e.get('ACTCALC_ALLOWED_HOSTS','actcalc.com,www.actcalc.com').split(',') if h.strip()),
            smtp_mode=e.get('ACTCALC_SMTP_MODE','starttls').lower().strip(),
            preview_token=e.get('ACTCALC_PREVIEW_TOKEN',''),
            legal_review_confirmed=truthy(e.get('ACTCALC_LEGAL_REVIEW_CONFIRMED','false')),
            smtp_delivery_verified=truthy(e.get('ACTCALC_SMTP_DELIVERY_VERIFIED','false')),
            backup_restore_verified=truthy(e.get('ACTCALC_BACKUP_RESTORE_VERIFIED','false')),
            live_device_verified=truthy(e.get('ACTCALC_LIVE_DEVICE_VERIFIED','false')),
        )

    def errors(self)->list[str]:
        errors=[]
        for name,okay in [('legal review',self.legal_review_confirmed),('live SMTP delivery',self.smtp_delivery_verified),('backup restoration',self.backup_restore_verified),('real-device QA',self.live_device_verified)]:
            if not okay:errors.append('Verification required: '+name)
        if self.preview_token and len(self.preview_token)<32:errors.append('ACTCALC_PREVIEW_TOKEN must be at least 32 characters when set')
        if len(self.contact_secret)<32: errors.append('ACTCALC_CONTACT_SECRET: minimum 32 characters')
        if len(self.admin_token)<32: errors.append('ACTCALC_ADMIN_TOKEN: minimum 32 characters')
        if self.contact_secret and self.contact_secret==self.admin_token:errors.append('Use different secrets')
        if not self.operator_name:errors.append('ACTCALC_OPERATOR_NAME must identify the data controller')
        if not self.privacy_email or '@' not in self.privacy_email:errors.append('ACTCALC_PRIVACY_EMAIL required')
        for key in ('smtp_host','smtp_user','smtp_password','smtp_sender','smtp_recipient'):
            if not getattr(self,key): errors.append(key.upper()+' required')
        if self.smtp_mode not in ('starttls','ssl'):errors.append('ACTCALC_SMTP_MODE must be starttls or ssl')
        if not 1<=self.smtp_port<=65535:errors.append('ACTCALC_SMTP_PORT invalid')
        if not self.db_path.is_absolute():errors.append('ACTCALC_DB_PATH must be absolute')
        if self.db_path.as_posix().startswith(('/tmp/', '/mnt/data/','/workspace/')):errors.append('ACTCALC_DB_PATH must be on persistent storage')
        if 'actcalc.com' not in self.allowed_hosts or 'www.actcalc.com' not in self.allowed_hosts:errors.append('Allowed hosts must include both actcalc domains')
        return errors

    @property
    def ready(self)->bool:
        return not self.errors()

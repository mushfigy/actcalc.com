from __future__ import annotations
import smtplib
from email.message import EmailMessage
from .config import Settings
from . import db

def deliver_one(settings:Settings,item:dict):
    mail=EmailMessage()
    mail['Subject']='ACTCalc — '+item['topic'].replace('\r',' ').replace('\n',' ')[:80]
    mail['From']=settings.smtp_sender
    mail['To']=settings.smtp_recipient
    mail['Reply-To']=item['email']
    mail.set_content('A contact request was stored by ACTCalc.\n\nName: '+item['name']+'\nEmail: '+item['email']+'\nTopic: '+item['topic']+'\n\n'+item['body'])
    if settings.smtp_mode=='ssl':
        with smtplib.SMTP_SSL(settings.smtp_host,settings.smtp_port,timeout=10) as smtp:
            smtp.login(settings.smtp_user,settings.smtp_password);smtp.send_message(mail)
    else:
        with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=10) as smtp:
            smtp.ehlo();smtp.starttls();smtp.ehlo();smtp.login(settings.smtp_user,settings.smtp_password);smtp.send_message(mail)

def send_batch(settings:Settings)->dict:
    counts={'sent':0,'failed':0}
    if not settings.smtp_host or not settings.smtp_sender:return counts
    for item in db.pending(settings.db_path):
        try:
            deliver_one(settings,item)
        except Exception:
            # Do not disclose SMTP credentials or remote errors to users.
            db.mark(settings.db_path,item['id'],'pending')
            counts['failed']+=1
        else:
            db.mark(settings.db_path,item['id'],'sent')
            counts['sent']+=1
    return counts

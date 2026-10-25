"""ACTCalc local-first application with persistent, secured enquiry processing.

The production service stays private by default and fails closed if its
operator, mail, secret or storage configuration is incomplete.
"""
from __future__ import annotations
import asyncio
import base64, binascii
from contextlib import asynccontextmanager, suppress
import hashlib, hmac, html, ipaddress, json, os, re, secrets, time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware
from .config import Settings
from . import db, mailer

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'static'
EMAIL_RE=re.compile(r'^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$',re.ASCII)
TOPICS={'Question','Feedback','Problem','Workflow setup','Privacy request'}


def script_csp(index:str)->str:
    hashes=[]
    for body in re.findall(r'<script(?:\s[^>]*)?>(.*?)</script\s*>',index,flags=re.IGNORECASE|re.DOTALL):
        # hashes are immutable and calculated from the exact published HTML.
        import base64
        sha=base64.b64encode(hashlib.sha256(body.encode('utf-8')).digest()).decode()
        hashes.append("'sha256-"+sha+"'")
    return "default-src 'self'; script-src 'self' "+' '.join(hashes)+"; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; media-src 'self' blob: data:; worker-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests"

INDEX=ASSETS.joinpath('index.html').read_text('utf-8')
CSP=script_csp(INDEX)


def sanitize_email(raw:object)->str:
    if not isinstance(raw,str):raise ValueError('Enter a valid email.')
    v=raw.strip()
    if len(v)>254 or not EMAIL_RE.fullmatch(v) or any(c in v for c in '\r\n'):
        raise ValueError('Enter a valid email.')
    return v

def fields(payload:object)->dict:
    if not isinstance(payload,dict):raise ValueError('Invalid request.')
    name=str(payload.get('name','')).strip()
    topic=str(payload.get('topic','Question')).strip()
    message=payload.get('message','')
    if len(name)>100 or any(c in name for c in '\r\n'):raise ValueError('Name must be one line and no more than 100 characters.')
    if topic not in TOPICS:raise ValueError('Choose an available topic.')
    if not isinstance(message,str) or not 10<=len(message.strip())<=5000:
        raise ValueError('Message must contain 10–5000 characters.')
    return {'name':name,'email':sanitize_email(payload.get('email','')),'topic':topic,'message':message.strip()}


def ip_hash(settings:Settings,request:Request)->str:
    # Never trust X-Forwarded-For unless the trusted proxy has overwritten it.
    addr=request.client.host if request.client else 'unknown'
    return hmac.new(settings.contact_secret.encode(),('ip:'+addr).encode(),hashlib.sha256).hexdigest()


def issue_nonce(settings:Settings,request:Request)->str:
    ts=str(int(time.time()))
    rnd=secrets.token_urlsafe(20)
    body=f'v1.{ts}.{rnd}'
    sig=hmac.new(settings.contact_secret.encode(),(body+'.'+ip_hash(settings,request)).encode(),hashlib.sha256).hexdigest()
    return body+'.'+sig


def validate_nonce(settings:Settings,request:Request,value:object)->str:
    if not isinstance(value,str) or len(value)>190:return ''
    parts=value.split('.')
    if len(parts)!=4 or parts[0]!='v1':return ''
    try:ts=int(parts[1])
    except ValueError:return ''
    if abs(time.time()-ts)>720:return ''
    body='.'.join(parts[:3])
    expected=hmac.new(settings.contact_secret.encode(),(body+'.'+ip_hash(settings,request)).encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,parts[3]):return ''
    return hashlib.sha256(value.encode()).hexdigest()


def same_origin(request:Request,settings:Settings)->bool:
    # JSON fetch requests from real browsers include Origin. In future SDKs the
    # referring page may be present instead, but both must match this host.
    provided=request.headers.get('origin') or request.headers.get('referer','')
    if not provided:return False
    origin=urlsplit(provided)
    host=request.headers.get('host','').lower()
    if not origin.hostname or origin.netloc.lower()!=host:return False
    if origin.scheme!='https' and not (settings.local_dev and origin.scheme=='http' and origin.hostname in ('localhost','127.0.0.1','testserver')):
        return False
    return True


def preview_allowed(request:Request,settings:Settings)->bool:
    """Password protected staging; no bypass of the public launch gate."""
    if len(settings.preview_token)<32:return False
    header=request.headers.get('authorization','')
    if not header.startswith('Basic '):return False
    try:
        value=base64.b64decode(header[6:],validate=True).decode('utf-8')
        username,sep,password=value.partition(':')
    except (binascii.Error, UnicodeDecodeError, ValueError):return False
    return bool(sep) and hmac.compare_digest(username,'preview') and hmac.compare_digest(password,settings.preview_token)


def access_allowed(request:Request,settings:Settings)->bool:
    if settings.public and settings.ready:return True
    if preview_allowed(request,settings):return True
    if not settings.local_dev:return False
    ip=request.client.host if request.client else ''
    try:return ipaddress.ip_address(ip).is_loopback
    except ValueError:return False


def page(name:str,title:str,body:str)->HTMLResponse:
    return HTMLResponse(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)} | ACTCalc</title><style>body{{font:16px/1.65 system-ui,Arial,sans-serif;color:#dce8ee;background:#071824;margin:0}}main{{max-width:720px;margin:4rem auto;padding:0 1.3rem}}a{{color:#a9d7eb}}h1,h2{{line-height:1.25}}footer{{border-top:1px solid #41515b;padding-top:1rem;margin-top:3rem;font-size:.9rem}}</style></head><body><main><p><a href="/">← ACTCalc</a></p><h1>{html.escape(title)}</h1>{body}<footer>ACTCalc — <a href="/privacy">Privacy</a> · <a href="/terms">Terms and limitations</a></footer></main></body></html>''')


def privacy(settings:Settings)->HTMLResponse:
    owner=html.escape(settings.operator_name or '[Operator identity pending]')
    email=html.escape(settings.privacy_email or '[Privacy contact email pending]')
    return page('privacy','Privacy information',f'''<p>ACTCalc is operated by <strong>{owner}</strong>. Privacy enquiries: <strong>{email}</strong>.</p>
    <h2>Calculator data</h2><p>Calculations and saved works are stored in the browser on the user's device. ACTCalc does not receive them merely because a calculation is performed. Browser storage can be cleared; export a backup to retain data.</p>
    <h2>Contact messages</h2><p>If you send an enquiry, ACTCalc processes the supplied name, email, topic and message to respond. The site stores contact requests on its server for up to 30 days, then deletes them. A restricted operator inbox can view them. The sending email provider also processes the message for delivery; its retention practices apply separately. We use a pseudonymous identifier derived from the connection address to deter spam and rate-limit submissions.</p>
    <h2>Security and rights</h2><p>Use nonconfidential examples. Do not enter passwords, protected engineering designs or patient/financial records in a contact request. Contact the operator using the address above to request access, correction or deletion of your message. Depending on the applicable law, you may have additional privacy rights. Standard server, CDN and host logs may be processed by your hosting provider subject to its own terms.</p>
    <p>This notice must be reviewed and completed for the actual legal operator, hosting provider and jurisdiction before public activation.</p>''')


def terms()->HTMLResponse:
    return page('terms','Terms and engineering limitations','''<p>ACTCalc is a browser-based calculation, engineering reference, and export tool offered as a general aid, not as a certified engineering design, safety analysis, or professional engineering sign-off.</p>
    <h2>Verify results independently</h2><p>Check model assumptions, input dimensions, units, correlations, validity ranges, and outputs against trusted references before using them in any design or operational decision. Specialized calculations were smoke-tested but have not all been independently validated to a professional standard. Do not use the tool as the sole basis for safety-critical activities.</p>
    <h2>Local data</h2><p>Saved work is stored in the browser used to create it and is not automatically shared or backed up across devices. Export a backup regularly.</p>
    <h2>No purchases created by enquiries</h2><p>A contact form or workflow brief does not create an order, paid subscription, scope of work, engineering commitment, or payment obligation. Any paid work requires separate agreement.</p>
    <p>These terms require operator review for the actual jurisdiction before public access.</p>''')


def create_app(settings:Settings|None=None):
    settings=settings or Settings.from_env()

    async def housekeeper():
        while True:
            await asyncio.sleep(60)
            with suppress(Exception):
                await asyncio.to_thread(db.purge,settings.db_path)
                await asyncio.to_thread(mailer.send_batch,settings)

    @asynccontextmanager
    async def lifespan(app:FastAPI):
        # Avoid creating a database for intentionally blocked remote access.
        if settings.ready or settings.local_dev or len(settings.preview_token)>=32:db.initialize(settings.db_path)
        job=asyncio.create_task(housekeeper()) if settings.ready or settings.local_dev or len(settings.preview_token)>=32 else None
        try:yield
        finally:
            if job:
                job.cancel()
                with suppress(asyncio.CancelledError):await job

    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=[*settings.allowed_hosts, *(['localhost','127.0.0.1','testserver'] if settings.local_dev else [])])
    app.add_middleware(GZipMiddleware,minimum_size=1500)

    @app.middleware('http')
    async def restrict_and_secure(req:Request,call_next):
        if req.url.path!='/api/health' and not access_allowed(req,settings):
            if len(settings.preview_token)>=32:
                resp=PlainTextResponse('ACTCalc private preview requires authorization.',status_code=401,headers={'WWW-Authenticate':'Basic realm="ACTCalc prelaunch preview"'})
            else:
                resp=PlainTextResponse('This ACTCalc release is not publicly available.',status_code=503)
        else:
            try:resp=await call_next(req)
            except Exception:
                resp=PlainTextResponse('Service temporarily unavailable.',status_code=503)
        resp.headers['X-Content-Type-Options']='nosniff'
        resp.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        resp.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        resp.headers['X-Frame-Options']='DENY'
        resp.headers['Cross-Origin-Opener-Policy']='same-origin'
        resp.headers['Content-Security-Policy']=CSP
        if req.url.scheme=='https':resp.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        if req.url.path.startswith('/api/'):resp.headers['Cache-Control']='no-store'
        return resp

    @app.get('/api/health')
    def health():
        return {'status':'ok','public_release_configuration_ready':settings.ready,'public_access_enabled':settings.public and settings.ready}

    @app.get('/api/contact')
    def contact_challenge(req:Request):
        return {'ready':True,'nonce':issue_nonce(settings,req)}

    @app.post('/api/contact')
    async def contact_submit(req:Request):
        if not same_origin(req,settings):raise HTTPException(403,detail='Invalid request origin.')
        if not req.headers.get('content-type','').split(';')[0].lower()=='application/json':
            raise HTTPException(415,detail='Use JSON request content.')
        try:content_length=int(req.headers.get('content-length','0') or 0)
        except ValueError:raise HTTPException(400,detail='Invalid content length.')
        if content_length<0 or content_length>12500:raise HTTPException(413,detail='Message too large.')
        try:raw=await req.body()
        except Exception:raise HTTPException(400,detail='Invalid request.')
        if len(raw)>12500:raise HTTPException(413,detail='Message too large.')
        try:data=json.loads(raw)
        except (ValueError,UnicodeDecodeError):raise HTTPException(400,detail='Invalid JSON.')
        hash_=validate_nonce(settings,req,data.get('nonce') if isinstance(data,dict) else None)
        if not hash_:return JSONResponse({'accepted':False,'error':'Refresh the contact form and try again.'},status_code=403)
        if data.get('website'):
            return {'accepted':True,'message':'Your request has been accepted.'}
        try:values=fields(data)
        except ValueError as e:return JSONResponse({'accepted':False,'error':str(e)},status_code=422)
        saved,msg=db.insert(settings.db_path,values,hash_,ip_hash(settings,req))
        if not saved:return JSONResponse({'accepted':False,'error':msg},status_code=429)
        return {'accepted':True,'message':'Your message has been received and queued for delivery.'}

    def authorize(req:Request):
        auth=req.headers.get('authorization','')
        if not hmac.compare_digest(auth,'Bearer '+settings.admin_token):raise HTTPException(401,detail='Unauthorized')

    @app.get('/api/admin/messages')
    def admin_messages(req:Request):
        authorize(req)
        return {'messages':db.list_contacts(settings.db_path)}

    @app.delete('/api/admin/messages/{message_id}')
    def admin_delete(message_id:int,req:Request):
        authorize(req)
        return {'deleted':bool(db.delete(settings.db_path,message_id))}

    @app.get('/privacy')
    def privacy_route():return privacy(settings)

    @app.get('/terms')
    def terms_route():return terms()

    @app.get('/robots.txt',response_class=PlainTextResponse)
    def robots():
        return 'User-agent: *\nAllow: /\nSitemap: https://actcalc.com/sitemap.xml\n' if settings.public and settings.ready else 'User-agent: *\nDisallow: /\n'

    @app.get('/sitemap.xml')
    def sitemap():
        return PlainTextResponse('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://actcalc.com/</loc></url><url><loc>https://actcalc.com/privacy</loc></url><url><loc>https://actcalc.com/terms</loc></url></urlset>',media_type='application/xml')

    @app.get('/')
    def root():return FileResponse(ASSETS/'index.html',media_type='text/html',headers={'Cache-Control':'no-cache, must-revalidate'})

    @app.get('/sw.js')
    def sw():return FileResponse(ASSETS/'sw.js',media_type='text/javascript',headers={'Cache-Control':'no-cache, must-revalidate','Service-Worker-Allowed':'/'})

    @app.get('/manifest.webmanifest')
    def manifest():return FileResponse(ASSETS/'manifest.webmanifest',media_type='application/manifest+json')

    @app.get('/icons/{name}')
    def icon(name:str):
        if name not in ('actcalc-192.png','actcalc-512.png'):raise HTTPException(404,detail='Not found.')
        return FileResponse(ASSETS/'icons'/name,media_type='image/png')

    return app

app=create_app()

"""Prepare immutable ACTCalc app assets from the user-reviewed mobile HTML.
Runs at packaging time; no production secrets are embedded in the browser.
"""
from pathlib import Path
import re, hashlib, json, base64
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source'/'ACTCalc-Rev3-Mobile-Optimized.html'
if not SOURCE.exists():
    raise SystemExit('The reviewed mobile HTML was not found; do not package a substitute.')
s=SOURCE.read_text(encoding='utf-8')
assert 'globalThis.ACTOfflineReview=true;' in s
s=s.replace('globalThis.ACTOfflineReview=true;',"globalThis.ACTOfflineReview=(location.protocol==='file:');",1)
s=s.replace("'Proposed package: EUR 2,000 excluding VAT; scope subject to agreement.',", "'Pricing and scope are discussed before any commitment.',",1)
s=s.replace('Sending uses Resend to deliver to the ACT operator’s inbox; this site does not save the message body. Short-lived hashed identifiers help prevent spam.', 'Messages are stored for up to 30 days to support a reply. Short-lived anti-spam identifiers are used. Do not include passwords or confidential project data. See Privacy below.',1)
# Static policy links are only additions; do not rewrite calculator controls or mathematics.
footer='<nav class="act-legal-links" aria-label="Site information"><a href="/privacy">Privacy</a><a href="/terms">Terms & engineering limitations</a></nav>'
css='''<style id="act-production-legal">.act-legal-links{display:flex;flex-wrap:wrap;justify-content:center;gap:1.2rem;padding:16px 12px 24px;background:#071824;color:#c8d6df;font-size:13px}.act-legal-links a{color:inherit;text-underline-offset:3px}@media screen{.act-workspace .site-contact{display:flex!important;align-items:center;justify-content:flex-end;padding:9px 12px!important}.act-workspace .site-contact button{min-height:44px;color:#becfd6!important;font-size:14px}}@media(max-width:900px){.act-legal-links{padding-bottom:calc(24px + env(safe-area-inset-bottom))}}</style>'''
s=s.replace('</head>',css+'</head>',1)
s=s.replace('</body>',footer+'</body>',1)
s=s.replace('<button onclick=\"location.reload()\">Try again</button>', '<a href=\"/\">Try again</a>')
s=s.replace('<title>ACTCALC Rev3 — WORK1 Engineering Workspace</title>', '<title>ACTCalc — Engineering calculator</title>',1)
s,n=re.subn(r'data-product-build="[^"]+"','data-product-build="rev3-production-candidate"',s,count=1)
assert n==1,'The release build attribute was not found.'
s,n=re.subn(r'data-act-release="[^"]+"','data-act-release="rev3-candidate"',s,count=1)
assert n==1,'The release identifier was not found.'
s=s.replace('https://actcalc.com/social/actcalc-share.png','https://actcalc.com/icons/actcalc-512.png',1)
if '<link rel="canonical"' not in s:
    s=s.replace('</head>','<link rel="canonical" href="https://actcalc.com/"></head>',1)
# Inline custom module boot should be deployable on HTTP loopback or HTTPS host.
assert '/api/contact' in s and 'mobile-result-visibility.js' in s
(ROOT/'static'/'index.html').write_text(s, encoding='utf-8')
# Offline shell service worker: network-first navigation prevents stale pages after a release.
revision=hashlib.sha256(s.encode()).hexdigest()[:12]
sw=f'''const CACHE='actcalc-{revision}';\nconst SHELL=['/','/manifest.webmanifest','/icons/actcalc-192.png','/icons/actcalc-512.png'];\nself.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));\nself.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('actcalc-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));\nself.addEventListener('fetch',e=>{{const r=e.request;if(r.method!=='GET'||!r.url.startsWith(self.location.origin)||new URL(r.url).pathname.startsWith('/api/'))return;const path=new URL(r.url).pathname;if(r.mode==='navigate'){{e.respondWith(fetch(r).catch(()=>caches.match('/')));return;}}if(SHELL.includes(path)){{e.respondWith(caches.match(r).then(c=>c||fetch(r)));}}}});\n'''
(ROOT/'static'/'sw.js').write_text(sw)
manifest={"name":"ACTCalc — Engineering calculator","short_name":"ACTCalc","start_url":"/","scope":"/","display":"standalone","theme_color":"#061722","background_color":"#061722","icons":[{"src":"/icons/actcalc-192.png","sizes":"192x192","type":"image/png","purpose":"any maskable"},{"src":"/icons/actcalc-512.png","sizes":"512x512","type":"image/png","purpose":"any maskable"}]}
(ROOT/'static'/'manifest.webmanifest').write_text(json.dumps(manifest,ensure_ascii=False))
try:
 from PIL import Image
 from io import BytesIO
 import cairosvg
 icon=re.search(r'<link\s+rel="icon"\s+href="data:image/svg\+xml;base64,([^"\s]+)',s)
 if not icon:raise ValueError('Missing existing ACT brand mark')
 logo=base64.b64decode(icon.group(1))
 for sz in (192,512):
  rendered=Image.open(BytesIO(cairosvg.svg2png(bytestring=logo,output_width=int(sz*.82),output_height=int(sz*.82)))).convert('RGBA')
  background=Image.new('RGBA',(sz,sz),'#071824')
  background.alpha_composite(rendered,((sz-rendered.width)//2,(sz-rendered.height)//2))
  background.convert('RGB').save(ROOT/'static'/'icons'/f'actcalc-{sz}.png')
except Exception as exc:
 raise SystemExit(f'Cannot build official brand PWA icons: {exc}')
print('Prepared frontend, SW revision',revision)

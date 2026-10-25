"""Real Chromium UI smoke checks with HTML injection.

The cloud environment denies localhost navigation. Backend HTTP is exercised
separately. This script is NOT proof of live-domain deployment or iOS Safari.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import os, shutil
from html import escape
from playwright.sync_api import sync_playwright
from backend.app import CSP

HTML=Path(__file__).resolve().parents[1].joinpath('static/index.html').read_text()


def open_page(browser,width=390,height=844,csp=True):
 p=browser.new_page(viewport={'width':width,'height':height})
 p._errors=[]
 p.on('pageerror',lambda exc:p._errors.append(str(exc)))
 p.on('console',lambda msg:p._errors.append('console: '+msg.text[:200]) if msg.type=='error' else None)
 # Replaces inaccessible about:blank storage with a deterministic in-memory shim.
 # Avoid asserting this is real site-origin persistence.
 p.evaluate('''() => { const store={}; Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>store[k]??null,setItem:(k,v)=>{store[k]=String(v)},removeItem:k=>{delete store[k]},clear:()=>Object.keys(store).forEach(k=>delete store[k])}}); }''')
 html=HTML
 if csp:
  meta='<meta http-equiv="Content-Security-Policy" content="'+escape(CSP,quote=True)+'">'
  html=html.replace('<head>','<head>'+meta,1)
 p.set_content(html,wait_until='domcontentloaded',timeout=30000)
 p.locator('.workspace-calculate').wait_for()
 return p


def check(browser,width):
 p=open_page(browser,width)
 size=p.evaluate('''() => ({scrollWidth:document.documentElement.scrollWidth, innerWidth:innerWidth})''')
 assert size['scrollWidth']<=width+2,(width,size)
 assert p.locator('#expression').is_visible()
 assert p.locator('.workspace-calculate').is_visible()
 # Most important mobile condition: result is near calculation, not obscured by a keypad.
 if width<=500:
  bar=p.locator('.workspace-calculate').bounding_box()
  out=p.get_by_text('Your result appears here').first.bounding_box()
  assert bar['y']<844+150 and out['y']<844+200,(width,bar,out)
  assert p.locator('.site-contact [data-contact="open"]').is_visible(),f'Contact unreachable at {width}px'
 p.locator('#expression').fill('2+3*4')
 p.locator('.workspace-calculate').click()
 assert p.get_by_text('14',exact=True).count()>0,(width,p.locator('body').inner_text()[-800:])
 assert not p._errors,(width,p._errors[:8])
 if width==390:
  # A second calculation must update without an old result being treated as current.
  p.locator('#expression').fill('3^2')
  p.locator('.workspace-calculate').click()
  assert p.get_by_text('9',exact=True).count()>0
  assert 'saved work' in p.locator('body').inner_text().lower()
  p.get_by_role('button',name='Graph',exact=True).click()
  assert p.locator('#plot-formula').is_visible()
  p.locator('#plot-formula').fill('sin(x)')
  p.locator('.workspace-calculate').click()
  assert 'points' in p.locator('body').inner_text().lower()
  p.get_by_role('button',name='Units',exact=True).click()
  assert p.locator('#convert-value').is_visible()
  p.locator('#convert-value').fill('2')
  p.locator('.workspace-calculate').click()
  assert 'Result' in p.locator('body').inner_text() or 'Convert' in p.locator('body').inner_text()
  p.get_by_role('button',name='Functions',exact=True).click()
  assert p.get_by_text('Pipe pressure drop').count()>0
  # Functions is a modal browser; dismiss it before operating the footer.
  p.keyboard.press('Escape')
  # Contact is tested without transmitting anything outside the browser.
  p.evaluate("""() => { window.fetch=async (url,options) => {
      if(options?.method==='POST')return {ok:true,json:async()=>({accepted:true,message:'Received for processing'})};
      return {ok:true,json:async()=>({ready:true,nonce:'SYNTHETIC-CONTACT-TOKEN'})};
  }; }""")
  p.locator('.site-contact [data-contact="open"]').click()
  assert p.locator('#contact-form').is_visible()
  p.locator('#contact-send').wait_for(state='visible')
  p.locator('[name=email]').fill('qa@example.org')
  p.locator('[name=message]').fill('This is a mock browser message for release QA only.')
  p.locator('#contact-send').click()
  assert 'Received for processing' in p.locator('#contact-status').inner_text()
 assert not p._errors,(width,p._errors[:12])
 print('UI PASS:',width,'px')
 p.close()


if __name__=='__main__':
 with sync_playwright() as pw:
  chrome=os.environ.get('ACTCALC_CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('chromium-browser')
  options={'executable_path':chrome} if chrome else {}
  b=pw.chromium.launch(headless=True,args=['--no-sandbox'],**options)
  for width in (320,390,768,1024,1440):check(b,width)
  b.close()

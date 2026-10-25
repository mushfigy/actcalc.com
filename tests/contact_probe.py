from playwright.sync_api import sync_playwright
from pathlib import Path
from backend.app import CSP
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 p=b.new_page(viewport={'width':390,'height':844})
 p.evaluate('''() => { window.fetch = async (url,opts)=>{ window.lastFetch=[url,opts||null]; if(opts?.method==='POST') return {ok:true,json:async()=>({accepted:true,message:'Received for processing'})};return {ok:true,json:async()=>({ready:true,nonce:'TEST-TOKEN'})}; }; }''')
 p.set_content(Path('/mnt/data/ACTCalc-Production-Release/static/index.html').read_text(),wait_until='domcontentloaded')
 text=p.locator('body').inner_text()
 print('contact presence?', 'Contact' in text,'web text last',text[-400:])
 for v in p.locator('button:visible').all():
  if 'contact' in v.inner_text().lower() or 'help' in v.inner_text().lower():print('button',v.inner_text(),v.get_attribute('data-contact'))
 print('footer',p.locator('.site-contact').count())
 if p.locator('.site-contact button').count():
  p.locator('.site-contact button').click()
  print('dialog open?',p.locator('#contact-form').is_visible())
  print('disabled?',p.locator('#contact-send').is_disabled())
  p.wait_for_timeout(1800)
  print('disabled after token?',p.locator('#contact-send').is_disabled())
  p.locator('[name=email]').fill('qa@example.org')
  p.locator('[name=message]').fill('Hello, this is a QA example only.')
  p.locator('#contact-send').click()
  print('sent payload',p.evaluate('window.lastFetch'))
  print('status',p.locator('#contact-status').inner_text())
 b.close()

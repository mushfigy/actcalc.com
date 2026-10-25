from playwright.sync_api import sync_playwright
from pathlib import Path
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 p=b.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
 errors=[]
 p.on('pageerror',lambda e:errors.append(str(e)))
 p.on('console',lambda msg:errors.append('console:'+msg.text) if msg.type=='error' else None)
 html=Path('/mnt/data/ACTCalc-Production-Release/static/index.html').read_text()
 p.set_content(html,wait_until='domcontentloaded',timeout=30000)
 p.wait_for_timeout(1200)
 print('embedded preview', 'title',p.title())
 print('text:',p.locator('body').inner_text()[:1800]);print('errors',errors[:12]);print('inputs')
 for i in p.locator('input').all()[:20]:print(i.get_attribute('id'),i.get_attribute('placeholder'),i.get_attribute('type'))
 p.screenshot(path='/mnt/data/ACTCalc-Production-Release/tests/initial_browser.png')
 b.close()

from playwright.sync_api import sync_playwright
from pathlib import Path
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 p=b.new_page(viewport={'width':390,'height':844})
 # Storage fallback for about:blank test only: site-origin browser storage is verified only after hosting.
 p.evaluate('''() => { const state={}; Object.defineProperty(window,'localStorage',{configurable:true, value:{getItem:k=>state[k]??null,setItem:(k,v)=>state[k]=String(v),removeItem:k=>delete state[k],clear:()=>Object.keys(state).forEach(k=>delete state[k])}}); }''')
 p.set_content(Path('/mnt/data/ACTCalc-Production-Release/static/index.html').read_text(),wait_until='domcontentloaded')
 print('storage warning',p.get_by_text('Browser storage is unavailable.').count())
 p.locator('#expression').fill('2+3*4')
 p.locator('.workspace-calculate').click()
 print('MATH:',p.locator('body').inner_text()[-450:])
 p.get_by_role('button',name='Units',exact=True).click()
 print('UNITS ids',[(x.get_attribute('id'),x.get_attribute('placeholder')) for x in p.locator('input:visible').all()[:10]])
 print('UNITS text',p.locator('body').inner_text()[:850])
 p.get_by_role('button',name='Graph',exact=True).click()
 print('GRAPH ids',[(x.get_attribute('id'),x.get_attribute('placeholder')) for x in p.locator('input:visible').all()[:10]])
 print('GRAPH text',p.locator('body').inner_text()[:850])
 p.get_by_role('button',name='Functions',exact=True).click()
 print('FUNCTIONS text',p.locator('body').inner_text()[:1050])
 b.close()

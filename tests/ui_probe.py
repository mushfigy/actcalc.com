from playwright.sync_api import sync_playwright
from pathlib import Path
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 p=b.new_page(viewport={'width':390,'height':844})
 p.set_content(Path('/mnt/data/ACTCalc-Production-Release/static/index.html').read_text(),wait_until='domcontentloaded')
 p.wait_for_timeout(200)
 for el in p.locator('button:visible').all()[:90]:
  print(el.inner_text().replace('\n',' ').__repr__()[:60],el.get_attribute('id'),el.get_attribute('class'),el.get_attribute('data-workspace'),el.get_attribute('data-do'))
 print('keypad',p.locator('.keypad-grip').count())
 b.close()

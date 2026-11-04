const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('node:path');
const os = require('node:os');
const chrome = process.env.CHROME_PATH || (process.platform === 'win32'
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined);

(async () => {
  const browser = await chromium.launch({headless:true,executablePath:chrome});
  const page = await browser.newPage({viewport:{width:1440,height:900}});
  const output = process.env.SCREENSHOT_DIR || os.tmpdir();
  try {
    await page.goto(process.env.BASE_URL || 'http://localhost:18080',{waitUntil:'networkidle'});
    for (const [name,id] of [
      ['host','10000000-0000-0000-0000-000000000002'],
      ['company','10000000-0000-0000-0000-000000000003'],
      ['network','10000000-0000-0000-0000-000000000004'],
      ['admin','10000000-0000-0000-0000-000000000006']
    ]) {
      await page.locator('#actor').selectOption(id);
      await page.waitForFunction(userId => state.actor?.id === userId, id);
      await page.waitForTimeout(350);
      await page.screenshot({path:path.join(output,'ec-audit-'+name+'.png'),fullPage:true});
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

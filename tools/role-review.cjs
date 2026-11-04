const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('node:path');
const os = require('node:os');

const base = process.env.BASE_URL || 'http://localhost:18080';
const chrome = process.env.CHROME_PATH || (process.platform === 'win32'
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined);
const output = process.env.SCREENSHOT_DIR || os.tmpdir();
const roles = [
  ['private-host', '10000000-0000-0000-0000-000000000002'],
  ['company', '10000000-0000-0000-0000-000000000003'],
  ['network', '10000000-0000-0000-0000-000000000004'],
  ['administrator', '10000000-0000-0000-0000-000000000006']
];

(async () => {
  const browser = await chromium.launch({headless: true, executablePath: chrome});
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base, {waitUntil: 'networkidle'});
    for (const [role, userId] of roles) {
      await page.locator('#actor').selectOption(userId);
      await page.locator('main h1').waitFor();
      await page.waitForTimeout(200);
      console.log(role + ': ' + await page.locator('main h1').innerText());
      await page.screenshot({path: path.join(output, 'ec-role-' + role + '.png'), fullPage: true});
    }
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('#actor').selectOption('10000000-0000-0000-0000-000000000001');
    await page.locator('.map-pin').first().waitFor();
    await page.waitForTimeout(350);
    await page.screenshot({path: path.join(output, 'ec-role-driver-mobile.png'), fullPage: true});
    await page.locator('#actor').selectOption(roles[0][1]);
    await page.waitForTimeout(250);
    await page.screenshot({path: path.join(output, 'ec-role-private-host-mobile.png'), fullPage: true});
    console.log('page errors: ' + errors.length);
    if (errors.length) throw new Error(errors.join('\n'));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

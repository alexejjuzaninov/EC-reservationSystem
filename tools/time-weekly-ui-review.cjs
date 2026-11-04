const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('node:path');
const os = require('node:os');

const base = process.env.BASE_URL || 'http://localhost:18080';
const output = process.env.SCREENSHOT_DIR || os.tmpdir();
const chrome = process.env.CHROME_PATH || (process.platform === 'win32'
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined);

(async () => {
  const browser = await chromium.launch({headless:true,executablePath:chrome});
  const page = await browser.newPage({viewport:{width:1366,height:768}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.url().startsWith(base + '/api/') && response.status() >= 400)
      errors.push(response.status() + ' ' + response.url());
  });
  try {
    await page.goto(base,{waitUntil:'networkidle'});
    await page.locator('[data-time-search]').click();
    await page.locator('#time-search-dialog').waitFor({state:'visible'});
    await page.screenshot({path:path.join(output,'ec-time-search-dialog.png')});
    await page.locator('#search-duration').selectOption('120');
    const selected = await page.locator('#search-start-at').inputValue();
    await page.locator('#time-search-form button[type="submit"]').click();
    await page.waitForFunction(() => state.timeFilter?.durationMinutes === 120 && document.querySelector('#result-count')?.textContent.includes(' open'));
    assert.match(await page.locator('#result-count').innerText(), /of \d+ open/);
    assert(await page.locator('.result-card').count() > 0);
    await page.screenshot({path:path.join(output,'ec-time-search-results.png')});
    await page.locator('.result-card [data-book]').first().click();
    await page.locator('#booking-dialog').waitFor({state:'visible'});
    assert.equal(await page.locator('#start-at').inputValue(), selected);
    assert.equal((new Date(await page.locator('#end-at').inputValue()) - new Date(await page.locator('#start-at').inputValue())) / 60000,120);
    await page.locator('[data-close="booking-dialog"]').click();
    await page.locator('[data-clear-time]').click();
    await page.waitForFunction(() => !state.timeFilter);
    await page.locator('#actor').selectOption('10000000-0000-0000-0000-000000000002');
    await page.locator('.host-hero [data-schedule]').click();
    await page.locator('#schedule-dialog').waitFor({state:'visible'});
    assert.equal(await page.locator('.weekly-day').count(),7);
    await page.screenshot({path:path.join(output,'ec-weekly-hours-desktop.png')});
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(200);
    await page.screenshot({path:path.join(output,'ec-weekly-hours-mobile.png')});
    const opening = page.locator('.weekly-day').first().locator('.weekly-time-range .choice-control').first();
    await opening.locator('.control-trigger').click();
    assert(await opening.locator('.choice-option').count() > 20);
    await page.screenshot({path:path.join(output,'ec-weekly-dropdown-mobile.png')});
    await page.keyboard.press('Escape');
    await page.locator('[data-schedule-tab="blocks"]').click();
    assert(await page.locator('#block-start-at + .control-trigger').isVisible());
    assert.deepEqual(errors,[]);
    console.log('Time search, booking handoff, weekly schedule, and mobile view passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

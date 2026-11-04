const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.BASE_URL || 'http://localhost:18080';
const actor = '10000000-0000-0000-0000-000000000001';
const chrome = process.env.CHROME_PATH || (process.platform === 'win32'
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined);

(async () => {
  let browser, stationId;
  try {
    browser = await chromium.launch({headless:true,executablePath:chrome});
    const page = await browser.newPage({viewport:{width:1440,height:900}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base,{waitUntil:'networkidle'});
    await page.locator('.result-card .save-button:not(.is-saved)').first().waitFor();
    const save = page.locator('.result-card .save-button:not(.is-saved)').first();
    stationId = await save.getAttribute('data-save');
    await save.click();
    await page.waitForFunction(id => state.saved.some(station => station.id === id),stationId);
    await page.locator('#side-nav [data-view="saved"]').click();
    const card = page.locator('.saved-card').filter({has:page.locator(`[data-book="${stationId}"]`)});
    await card.waitFor();
    assert.equal(await card.locator('a[href*="google.com/maps/dir"]').count(),1);
    await card.locator(`[data-book="${stationId}"]`).click();
    await page.locator('#booking-dialog').waitFor({state:'visible'});
    await page.locator('[data-close="booking-dialog"]').click();
    await card.locator(`[data-save="${stationId}"]`).click();
    await card.waitFor({state:'detached'});
    assert.equal((await page.evaluate(id => state.saved.some(station => station.id === id),stationId)),false);
    assert.deepEqual(errors,[]);
    console.log('Saved charger, directions, reservation entry, and removal passed in the browser.');
  } finally {
    if (browser) await browser.close();
    if (stationId) {
      await fetch(base + '/api/saved-stations/' + stationId,
        {method:'DELETE',headers:{'X-Demo-User':actor}});
    }
  }
})().catch(error => {console.error(error);process.exitCode=1;});

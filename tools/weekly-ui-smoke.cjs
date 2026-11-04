const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const chrome = process.env.CHROME_PATH || (process.platform === 'win32'
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined);
const base = process.env.BASE_URL || 'http://localhost:18080';
const host = '10000000-0000-0000-0000-000000000002';

(async () => {
  const browser = await chromium.launch({headless:true,executablePath:chrome});
  const page = await browser.newPage({viewport:{width:1366,height:768}});
  let stationId, original;
  try {
    await page.goto(base,{waitUntil:'networkidle'});
    await page.locator('#actor').selectOption(host);
    await page.waitForFunction(() => state.actor?.kind === 'PERSON');
    stationId = await page.locator('.host-hero [data-schedule]').getAttribute('data-schedule');
    const response = await fetch(base + '/api/stations/' + stationId + '/weekly-hours',{headers:{'X-Demo-User':host}});
    original = await response.json();
    await page.locator('.host-hero [data-schedule]').click();
    await page.locator('#schedule-dialog').waitFor({state:'visible'});
    await page.locator('[data-weekly-preset="weekdays"]').click();
    assert.equal(await page.locator('.weekly-day').first().locator('select').first().inputValue(),'480');
    assert.equal(await page.locator('.weekly-day').last().locator('input[type="checkbox"]').isChecked(),false);
    await page.locator('#weekly-form button[type="submit"]').click();
    await page.waitForFunction(() => document.querySelector('#weekly-status')?.textContent === 'Your regular hours');
    const saved = await (await fetch(base + '/api/stations/' + stationId + '/weekly-hours',{headers:{'X-Demo-User':host}})).json();
    assert.equal(saved.configured,true);
    assert.equal(saved.days[0].opensMinute,480);
    assert.equal(saved.days[6].enabled,false);
    console.log('Weekly hours saved through the browser and verified through the API.');
  } finally {
    if (stationId && original) {
      const response = await fetch(base + '/api/stations/' + stationId + '/weekly-hours',{
        method:original.configured ? 'PUT' : 'DELETE',
        headers:{'X-Demo-User':host,'Content-Type':'application/json'},
        body:original.configured ? JSON.stringify({zoneId:original.zoneId,days:original.days}) : undefined
      });
      assert(response.ok,'Original weekly hours restored');
    }
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

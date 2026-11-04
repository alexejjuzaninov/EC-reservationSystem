const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.BASE_URL || 'http://localhost:18080';
const chrome = process.env.CHROME_PATH || (process.platform === 'win32'
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined);
const owner = '10000000-0000-0000-0000-000000000002';
const station = '20000000-0000-0000-0000-000000000002';
const reason = 'Browser schedule check ' + Date.now();

async function ownedBlocks() {
  const response = await fetch(base + '/api/stations/' + station + '/blocks', {headers:{'X-Demo-User':owner}});
  assert.equal(response.status, 200);
  return response.json();
}

(async () => {
  let browser;
  try {
    const slot = await (async () => {
      for (let day = 2; day <= 12; day++) {
        const start = new Date(); start.setUTCDate(start.getUTCDate() + day); start.setUTCHours(8,0,0,0);
        const end = new Date(start.getTime() + 60 * 60 * 1000);
        const url = new URL(base + '/api/stations/' + station + '/availability');
        url.searchParams.set('startAt',start.toISOString()); url.searchParams.set('endAt',end.toISOString());
        const check = await (await fetch(url)).json();
        if (check.available) return {start:start.toISOString(),end:end.toISOString()};
      }
      throw new Error('No free test slot');
    })();
    browser = await chromium.launch({headless:true,executablePath:chrome});
    const page = await browser.newPage({viewport:{width:1440,height:900}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base,{waitUntil:'networkidle'});
    await page.locator('#actor').selectOption(owner);
    await page.locator('#side-nav [data-view="stations"]').click();
    await page.locator('.owned-card [data-schedule]').first().click();
    await page.locator('#schedule-dialog').waitFor({state:'visible'});
    await page.evaluate(({start,end,reason}) => {
      document.querySelector('#block-start-at').value = localInput(new Date(start));
      document.querySelector('#block-end-at').value = localInput(new Date(end));
      document.querySelector('#block-reason').value = reason;
      window.refreshCustomControls?.();
    },{...slot,reason});
    await page.locator('#block-form button[type="submit"]').click();
    const row = page.locator('.schedule-block').filter({hasText:reason});
    await row.waitFor();
    assert.equal(await row.count(),1);
    await row.locator('[data-remove-block]').click();
    await row.waitFor({state:'detached'});
    assert.equal((await ownedBlocks()).some(block => block.reason === reason),false);
    assert.deepEqual(errors,[]);
    console.log('Host schedule was created and removed through the browser.');
  } finally {
    if (browser) await browser.close();
    const leftover = (await ownedBlocks()).find(block => block.reason === reason);
    if (leftover) {
      await fetch(base + '/api/stations/' + station + '/blocks/' + leftover.id,
        {method:'DELETE',headers:{'X-Demo-User':owner}});
    }
  }
})().catch(error => {console.error(error);process.exitCode=1;});

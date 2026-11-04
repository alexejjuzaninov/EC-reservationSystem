const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('node:path');
const os = require('node:os');

const base = process.env.BASE_URL || 'http://localhost:18080';
const chrome = process.env.CHROME_PATH || (process.platform === 'win32'
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined);
const output = process.env.SCREENSHOT_DIR || os.tmpdir();
const roles = [
  ['driver', '10000000-0000-0000-0000-000000000001', ['discover','saved','trips','inbox']],
  ['host', '10000000-0000-0000-0000-000000000002', ['overview','stations','bookings','inbox']],
  ['company', '10000000-0000-0000-0000-000000000003', ['fleet','bookings','inbox']],
  ['network', '10000000-0000-0000-0000-000000000004', ['network','stations','bookings','inbox']],
  ['admin', '10000000-0000-0000-0000-000000000006', ['control','catalog','reviews','bookings','inbox']]
];

(async () => {
  const browser = await chromium.launch({headless: true, executablePath: chrome});
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.url().startsWith(base + '/api/') && response.status() >= 400)
      errors.push(response.status() + ' ' + response.url());
  });
  try {
    await page.goto(base, {waitUntil:'networkidle'});
    assert.equal(await page.locator('.preview-pill').count(), 0);
    assert.equal(await page.getByText('140,000+ sample locations').count(), 0);
    assert(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight + 2),
      'Desktop discovery fits in the viewport');
    await page.setViewportSize({width:1366,height:768});
    await page.waitForTimeout(150);
    assert(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight + 2),
      'Laptop discovery fits in the viewport');
    await page.setViewportSize({width:1440,height:900});
    await page.waitForTimeout(150);
    assert.equal(await page.locator('#country-filter + .control-trigger').count(), 1);
    await page.locator('#country-filter + .control-trigger').click();
    assert(await page.locator('#country-filter').locator('xpath=..').locator('.choice-option').count() >= 2);
    await page.keyboard.press('Escape');
    await page.locator('#actor + .control-trigger').click();
    await page.locator('#actor').locator('xpath=..').locator('.choice-option').filter({hasText:'Mark'}).click();
    await page.waitForFunction(() => state.actor?.name === 'Mark');
    for (const [role, userId, views] of roles) {
      await page.locator('#actor').selectOption(userId);
      await page.waitForFunction(id => state.actor?.id === id && document.querySelector('#side-nav .nav-item'), userId);
      for (const view of views) {
        await page.locator('#side-nav [data-view="' + view + '"]').click();
        await page.locator('#main-content .view').waitFor();
        if (view === 'catalog') {
          await page.locator('.catalog-row').first().waitFor();
          assert((await page.locator('#catalog-total').innerText()).includes('141,354'));
          await page.screenshot({path:path.join(output,'ec-review-admin-catalog.png'),fullPage:true});
          await page.setViewportSize({width:390,height:844});
          await page.waitForTimeout(250);
          await page.screenshot({path:path.join(output,'ec-review-admin-catalog-mobile.png'),fullPage:true});
          await page.setViewportSize({width:1440,height:900});
          await page.waitForTimeout(150);
          await page.locator('#catalog-pagination').getByRole('button',{name:'Next'}).click();
          await page.waitForFunction(() => state.adminCatalog.result?.page === 1);
          await page.locator('#catalog-query').fill('Brno');
          await page.waitForFunction(() => state.adminCatalog.result?.items?.every(item =>
            /brno/i.test(item.name + item.city + item.ownerName)));
          await page.locator('#catalog-query').fill('');
          await page.waitForFunction(() => state.adminCatalog.result?.total === 141354);
          await page.locator('#catalog-jump').fill('100');
          await page.locator('#catalog-jump-form button').click();
          await page.waitForFunction(() => state.adminCatalog.result?.page === 99);
          await page.locator('.catalog-row [data-telemetry]').first().click();
          await page.locator('#telemetry-dialog').waitFor({state:'visible'});
          assert((await page.locator('#telemetry-content').innerText()).includes('Generated preview'));
          await page.locator('[data-close="telemetry-dialog"]').click();
          await page.locator('.catalog-row [data-schedule]').first().click();
          await page.locator('#schedule-dialog').waitFor({state:'visible'});
          assert.equal(await page.locator('.weekly-day').count(),7);
          await page.locator('[data-schedule-tab="blocks"]').click();
          assert(await page.locator('#block-start-at + .control-trigger').count());
          await page.locator('[data-close="schedule-dialog"]').click();
        }
        if (view === 'saved') {
          await page.locator('.saved-card').first().waitFor();
          assert(await page.locator('.saved-card').count() >= 2);
          assert(await page.locator('.saved-card a[href*="google.com/maps/dir"]').count() >= 2);
          assert.match(await page.locator('.saved-card a[href*="google.com/maps/dir"]').first().getAttribute('href'), /destination=\d+\.\d+%2C\d+\.\d+/);
          await page.waitForTimeout(300);
          await page.screenshot({path:path.join(output,'ec-review-saved-desktop.png'),fullPage:true});
          await page.setViewportSize({width:390,height:844});
          await page.waitForTimeout(320);
          await page.screenshot({path:path.join(output,'ec-review-saved-mobile.png'),fullPage:true});
          await page.setViewportSize({width:1440,height:900});
          await page.waitForTimeout(320);
        }
        if (role === 'host' && view === 'stations') {
          await page.locator('.owned-card [data-schedule]').first().click();
          await page.locator('#schedule-dialog').waitFor({state:'visible'});
          assert((await page.locator('#schedule-station-name').innerText()).length > 0);
          await page.screenshot({path:path.join(output,'ec-review-host-schedule.png')});
          assert.equal(await page.locator('.weekly-day').count(),7);
          await page.locator('[data-schedule-tab="blocks"]').click();
          await page.locator('#block-start-at + .control-trigger').click();
          await page.screenshot({path:path.join(output,'ec-review-host-schedule-calendar.png')});
          await page.keyboard.press('Escape');
          await page.setViewportSize({width:390,height:844});
          await page.waitForTimeout(200);
          await page.screenshot({path:path.join(output,'ec-review-host-schedule-mobile.png')});
          await page.setViewportSize({width:1440,height:900});
          await page.locator('[data-close="schedule-dialog"]').click();
        }
        if (view === 'trips' || view === 'bookings') {
          await page.locator('.booking-row').first().waitFor();
          if (view === 'trips') {
            assert(await page.locator('.next-trip').count());
            assert.match(await page.locator('.next-trip a[href*="google.com/maps/dir"]').getAttribute('href'), /destination=\d+\.\d+%2C\d+\.\d+/);
            await page.waitForTimeout(260);
            await page.screenshot({path:path.join(output,'ec-review-trips-desktop.png'),fullPage:true});
            await page.setViewportSize({width:390,height:844});
            await page.waitForTimeout(260);
            await page.screenshot({path:path.join(output,'ec-review-trips-mobile.png'),fullPage:true});
            await page.setViewportSize({width:1440,height:900});
            await page.waitForTimeout(260);
          }
          await page.locator('[data-booking-status="CANCELLED"]').click();
          await page.waitForFunction(() => state.bookingPager.result?.items?.every(item => item.status === 'CANCELLED'));
          await page.locator('[data-booking-status=""]').click();
          await page.locator('.booking-row').first().waitFor();
        }
        console.log(role + ' / ' + view + ': ' + (await page.locator('#main-content h1').first().innerText()).replace(/\s+/g,' '));
      }
    }
    await page.locator('#actor').selectOption(roles[0][1]);
    await page.locator('.result-card [data-book]').first().waitFor();
    await page.locator('.result-card [data-book]').first().click();
    await page.locator('#booking-dialog').waitFor({state:'visible'});
    await page.locator('#start-at + .control-trigger').click();
    await page.screenshot({path:path.join(output,'ec-review-calendar-open.png')});
    await page.locator('.date-control .control-panel:not([hidden]) .calendar-day:not(:disabled)').last().click();
    await page.locator('.date-control .control-panel:not([hidden]) .calendar-apply').click();
    assert(await page.locator('#start-at').inputValue());
    await page.screenshot({path:path.join(output,'ec-review-booking-calendar.png')});
    await page.locator('[data-close="booking-dialog"]').click();
    await page.setViewportSize({width:390,height:620});
    await page.waitForTimeout(200);
    await page.locator('.result-card [data-book]').first().click();
    await page.locator('#start-at + .control-trigger').click();
    await page.screenshot({path:path.join(output,'ec-review-booking-calendar-mobile.png')});
    await page.keyboard.press('Escape');
    if (await page.locator('#booking-dialog').isVisible()) await page.locator('[data-close="booking-dialog"]').click();
    console.log('page errors: ' + errors.length);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

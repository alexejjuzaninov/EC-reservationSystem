const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const baseUrl = process.env.BASE_URL || 'http://localhost:18080';
const chrome = process.env.CHROME_PATH || (process.platform === 'win32'
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined);
const users = {
  anna: '10000000-0000-0000-0000-000000000001',
  host: '10000000-0000-0000-0000-000000000002',
  company: '10000000-0000-0000-0000-000000000003',
  platform: '10000000-0000-0000-0000-000000000004',
  mark: '10000000-0000-0000-0000-000000000005',
  admin: '10000000-0000-0000-0000-000000000006'
};

(async () => {
  const browser = await chromium.launch({headless: true, executablePath: chrome});
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.status() >= 400 && response.url().startsWith(baseUrl)) {
      errors.push(response.status() + ' ' + response.url());
    }
  });
  try {
    await page.goto(baseUrl, {waitUntil: 'networkidle'});
    await page.locator('.map-pin').first().waitFor();
    assert.equal(await page.locator('main h1').innerText(), 'Find your next charge.');
    const map = await page.locator('#explore-map').boundingBox();
    const markerBoxes = await page.locator('.map-pin').evaluateAll(nodes => nodes.map(node => {
      const box = node.getBoundingClientRect();
      return {left: box.left, right: box.right, top: box.top, bottom: box.bottom};
    }));
    assert(markerBoxes.length > 4 && markerBoxes.length < 32);
    assert(markerBoxes.every(box => box.left >= map.x - 2 && box.right <= map.x + map.width + 2
      && box.top >= map.y - 2 && box.bottom <= map.y + map.height + 2), 'Map markers stay inside their panel');
    const center = markerBoxes.filter(box => {
      const x = (box.left + box.right) / 2;
      const y = (box.top + box.bottom) / 2;
      return x > map.x + map.width * .32 && x < map.x + map.width * .68
        && y > map.y + map.height * .32 && y < map.y + map.height * .68;
    });
    assert(center.length >= 3, 'Central Prague has visible clusters');
    await page.locator('#city-filter').fill('Tábor');
    await page.waitForFunction(() => state.map?.getZoom() === 12 && state.mapTotal === 600);
    assert.equal(await page.locator('#place-filter option:checked').innerText(), 'Tábor');
    await page.locator('#country-filter').selectOption('US');
    await page.waitForFunction(() => state.country === 'US' && state.mapTotal > 100);
    assert((await page.locator('.result-card').first().innerText()).includes('$'));
    await page.locator('#country-filter').selectOption('CZ');
    await page.waitForFunction(() => state.country === 'CZ' && state.mapTotal > 10000);

    const charger = page.locator('.result-card').filter({hasText: 'Stromovka Home Charger'}).first();
    const stationId = await charger.locator('[data-book]').getAttribute('data-book');
    await charger.locator('.result-main').click();
    await page.locator('.map-popup').waitFor();
    assert(await page.evaluate(() => state.map.getZoom()) >= 15);
    await page.locator('.map-popup button').click();
    await page.locator('#booking-dialog').waitFor({state: 'visible'});
    const chosen = new Date(Date.now() + (7 + Math.floor(Math.random() * 20)) * 86400000);
    chosen.setHours(8 + Math.floor(Math.random() * 9), 0, 0, 0);
    const pad = value => String(value).padStart(2, '0');
    const local = date => date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate())
      + 'T' + pad(date.getHours()) + ':' + pad(date.getMinutes());
    await page.locator('#start-at').fill(local(chosen));
    await page.locator('#end-at').fill(local(new Date(chosen.getTime() + 3600000)));
    await page.waitForFunction(() => document.querySelector('#availability strong')?.textContent === 'Available');
    assert.equal(await page.locator('#book-button').isEnabled(), true);
    const start = await page.locator('#start-at').inputValue();
    const end = await page.locator('#end-at').inputValue();
    const [bookingResponse] = await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/api/bookings') && response.request().method() === 'POST'),
      page.locator('#book-button').click()
    ]);
    const bookingId = (await bookingResponse.json()).id;
    await page.locator('main h1').filter({hasText: 'Your trips'}).waitFor();
    await page.locator('.booking-row').filter({hasText: 'Stromovka'}).first().waitFor();

    await page.locator('#actor').selectOption(users.mark);
    await page.locator('main h1').filter({hasText: 'Find your next charge'}).waitFor();
    await page.evaluate(id => openBooking(id), stationId);
    await page.locator('#booking-dialog').waitFor({state: 'visible'});
    await page.locator('#start-at').fill(start);
    await page.locator('#end-at').fill(end);
    await page.locator('#end-at').dispatchEvent('change');
    await page.locator('#availability strong').filter({hasText: 'Unavailable'}).waitFor();
    assert(await page.locator('#book-button').isDisabled());
    await page.locator('[data-close="booking-dialog"]').click();

    await page.locator('#actor').selectOption(users.anna);
    await page.locator('#side-nav [data-view="trips"]').click();
    const cancelButton = page.locator('[data-cancel="' + bookingId + '"]');
    for (let index = 0; index < 10 && !await cancelButton.count(); index++) {
      await page.locator('[data-booking-page]').filter({hasText:'Next'}).click();
      await page.waitForFunction(pageNumber => state.bookingPager.result?.page === pageNumber, index + 1);
    }
    assert.equal(await cancelButton.count(), 1, 'Newly created reservation is reachable through pagination');
    await cancelButton.click();
    await page.locator('[data-payment="' + bookingId + '"]').locator('..').locator('.booking-badge').filter({hasText: 'Cancelled'}).waitFor();

    await page.locator('#actor').selectOption(users.company);
    await page.locator('main h1').filter({hasText: 'Every plug'}).waitFor();
    await page.locator('[data-add-station]').first().click();
    await page.locator('#picker-map .leaflet-overlay-pane path').waitFor();
    await page.locator('#station-country').selectOption('US');
    await page.locator('#picker-map .leaflet-overlay-pane path').waitFor();
    await page.locator('#station-country').selectOption('CZ');
    await page.locator('#picker-map .leaflet-overlay-pane path').waitFor();
    await page.locator('#station-city').fill('Brno');
    await page.locator('#pin-summary-title').filter({hasText: 'Pinned near Brno'}).waitFor();
    assert(Math.abs(Number(await page.locator('#station-latitude').inputValue()) - 49.19522) < .001);
    await page.locator('#station-city').fill('Praha');
    await page.locator('#pin-summary-title').filter({hasText: 'Pinned near Prague'}).waitFor();
    const name = 'Browser preview ' + Date.now();
    const city = 'BrowserCity' + Date.now();
    await page.locator('#station-form [name="name"]').fill(name);
    await page.locator('#station-form [name="city"]').fill(city);
    await page.locator('#station-form [name="address"]').fill('Preview Street 3');
    await page.locator('#station-form [name="accessNote"]').fill('Use the green gate');
    await page.locator('#station-submit').click();
    await page.locator('#station-dialog').waitFor({state: 'hidden'});
    await page.locator('.fleet-row').filter({hasText: name}).first().waitFor();
    assert((await page.locator('.fleet-row').filter({hasText: name}).innerText()).includes('In review'));

    await page.locator('#actor').selectOption(users.admin);
    await page.locator('main h1').filter({hasText: 'Keep the network'}).waitFor();
    const review = page.locator('.review-card').filter({hasText: name});
    await review.first().waitFor();
    await review.locator('[data-approve="true"]').click();
    await review.waitFor({state: 'detached'});

    await page.locator('#actor').selectOption(users.anna);
    await page.locator('main h1').filter({hasText: 'Find your next charge'}).waitFor();
    await page.locator('#city-filter').fill(city);
    await page.locator('#result-count').filter({hasText: '1 nearby'}).waitFor();
    await page.locator('.result-card').filter({hasText: name}).first().waitFor();

    for (const [id, heading] of [
      [users.host, "Make space for"],
      [users.company, 'Every plug'],
      [users.platform, 'Power where'],
      [users.admin, 'Keep the network']
    ]) {
      await page.locator('#actor').selectOption(id);
      await page.locator('main h1').filter({hasText: heading}).waitFor();
      assert.equal(await page.locator('#explore-map').count(), 0);
      assert.equal(await page.evaluate(() => document.body.scrollWidth <= innerWidth), true);
    }
    assert.equal(/[А-Яа-яЁё]/.test(await page.locator('body').innerText()), false);

    const mobile = await browser.newPage({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
    mobile.on('pageerror', error => errors.push('mobile: ' + error.message));
    await mobile.goto(baseUrl, {waitUntil: 'networkidle'});
    await mobile.locator('.map-pin').first().waitFor();
    assert.equal(await mobile.evaluate(() => document.body.scrollWidth <= innerWidth), true);
    await mobile.locator('#menu-button').click();
    await mobile.locator('#side-nav [data-view="trips"]').click();
    await mobile.locator('main h1').filter({hasText: 'Your trips'}).waitFor();
    for (const [id, heading] of [
      [users.host, 'Make space for'],
      [users.company, 'Every plug'],
      [users.admin, 'Keep the network']
    ]) {
      await mobile.locator('#actor').selectOption(id);
      await mobile.locator('main h1').filter({hasText: heading}).waitFor();
      assert.equal(await mobile.evaluate(() => document.body.scrollWidth <= innerWidth), true);
    }
    await mobile.close();

    assert.deepEqual(errors, []);
    process.stdout.write('PASS: desktop and mobile role layouts, map pins, booking conflict, picker, station creation, review, and English UI\n');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('node:path');
const os = require('node:os');

const base = process.env.BASE_URL || 'http://localhost:18080';
const chrome = process.env.CHROME_PATH || (process.platform === 'win32'
  ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined);
const output = process.env.SCREENSHOT_DIR || os.tmpdir();

(async () => {
  const browser = await chromium.launch({headless: true, executablePath: chrome});
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  const findings = {};
  async function inspect(label) {
    await page.locator('.map-pin').first().waitFor();
    await page.waitForTimeout(350);
    findings[label] = await page.evaluate(() => {
      const map = document.querySelector('#explore-map').getBoundingClientRect();
      const points = [...document.querySelectorAll('.map-pin')].map(node => {
        const box = node.getBoundingClientRect();
        return {x: (box.left + box.width / 2 - map.left) / map.width,
          y: (box.top + box.height / 2 - map.top) / map.height, text: node.innerText};
      });
      return {zoom: state.map.getZoom(), total: state.mapTotal,
        clustered: state.clusters.reduce((sum, cluster) => sum + cluster.count, 0),
        cards: state.stations.length, markers: points.length,
        centerMarkers: points.filter(p => p.x > .32 && p.x < .68 && p.y > .32 && p.y < .68).length,
        centerCounts: points.filter(p => p.x > .32 && p.x < .68 && p.y > .32 && p.y < .68).map(p => p.text)};
    });
    await page.screenshot({path: path.join(output, 'ec-map-' + label + '.png'), fullPage: true});
  }
  try {
    await page.goto(base, {waitUntil: 'networkidle'});
    await inspect('prague');
    await Promise.all([
      page.waitForResponse(response => response.url().includes('/api/map/explore')),
      page.locator('.map-pin-cluster.dense').first().click()
    ]);
    await inspect('prague-zoom');
    await page.locator('.result-card .result-main').first().click();
    await page.locator('.map-popup').waitFor();
    await page.screenshot({path: path.join(output, 'ec-map-focused.png'), fullPage: true});
    await page.locator('#place-filter').selectOption({label: 'Brno'});
    await page.waitForFunction(() => state.map.getZoom() === 11 && state.mapTotal >= 6000);
    await inspect('brno');
    await page.locator('#place-filter').selectOption({label: 'Ostrava'});
    await page.waitForFunction(() => state.map.getZoom() === 11 && state.mapTotal >= 5000 && state.mapTotal < 6000);
    await inspect('ostrava');
    await page.locator('#place-filter').selectOption({label: 'All Czechia'});
    await page.waitForFunction(() => state.map.getZoom() === 7 && state.mapTotal > 60000);
    await inspect('czechia');
    await page.locator('#city-filter').fill('Tábor');
    await page.waitForFunction(() => state.map.getZoom() === 12 && state.mapTotal === 600);
    await inspect('tabor-search');
    process.stdout.write(JSON.stringify(findings, null, 2));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});

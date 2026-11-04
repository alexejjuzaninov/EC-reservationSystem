const assert = require('node:assert/strict');

const base = process.env.EC_BASE_URL || 'http://localhost:18080';
const station = '20000000-0000-0000-0000-000000000002';
const driver = '10000000-0000-0000-0000-000000000001';
const owner = '10000000-0000-0000-0000-000000000002';
const admin = '10000000-0000-0000-0000-000000000006';

async function request(path, actor, method = 'GET', body) {
  const response = await fetch(base + '/api' + path, {
    method,
    headers: {'Content-Type':'application/json', 'X-Demo-User':actor},
    body: body && JSON.stringify(body)
  });
  const data = await response.json().catch(() => ({}));
  return {status:response.status, data};
}

async function run() {
  const stationInfo = await request('/stations/' + station, driver);
  assert.equal(stationInfo.status, 200);
  let startAt, endAt;
  for (let days = 2; days <= 12; days++) {
    const start = new Date(); start.setUTCDate(start.getUTCDate() + days); start.setUTCHours(8,0,0,0);
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    const candidate = await request(`/stations/${station}/availability?startAt=${start.toISOString()}&endAt=${end.toISOString()}`, driver);
    if (candidate.data.available) { startAt = start.toISOString(); endAt = end.toISOString(); break; }
  }
  assert(startAt, 'No free test slot was found');
  let blockId;
  try {
    const forbidden = await request('/stations/' + station + '/blocks', driver);
    assert.equal(forbidden.status, 403);
    const created = await request('/stations/' + station + '/blocks', owner, 'POST', {startAt,endAt,reason:'Schedule test'});
    assert.equal(created.status, 201, JSON.stringify(created.data));
    blockId = created.data.id;
    assert.equal((await request('/stations/' + station + '/blocks', owner)).data.some(block => block.id === blockId), true);
    assert.equal((await request('/stations/' + station + '/blocks', admin)).status, 200);
    const availability = await request(`/stations/${station}/availability?startAt=${startAt}&endAt=${endAt}`, driver);
    assert.equal(availability.data.available, false);
    assert.match(availability.data.reason, /blocked time/i);
    assert.equal((await request('/bookings', driver, 'POST', {stationId:station,startAt,endAt})).status, 409);
    assert.equal((await request('/stations/' + station + '/blocks', owner, 'POST', {startAt,endAt,reason:'Overlap'})).status, 409);
    console.log('Schedule creation, role access, booking exclusion, and overlap checks passed.');
  } finally {
    if (blockId) {
      const removed = await request('/stations/' + station + '/blocks/' + blockId, owner, 'DELETE');
      assert.equal(removed.status, 204);
      assert.equal((await request(`/stations/${station}/availability?startAt=${startAt}&endAt=${endAt}`, driver)).data.available, true);
      console.log('Temporary block removed; station availability restored.');
    }
  }
}

run().catch(error => { console.error(error); process.exitCode = 1; });

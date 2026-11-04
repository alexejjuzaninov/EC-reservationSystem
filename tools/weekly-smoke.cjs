const assert = require('node:assert/strict');

const base = process.env.BASE_URL || 'http://localhost:18080';
const host = '10000000-0000-0000-0000-000000000002';
const driver = '10000000-0000-0000-0000-000000000001';

async function request(path, user = host, options = {}) {
  const response = await fetch(base + '/api' + path, {
    ...options, headers:{'X-Demo-User':user,'Content-Type':'application/json',...(options.headers || {})}
  });
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(response.status + ' ' + JSON.stringify(data));
  return data;
}

(async () => {
  const station = (await request('/my-stations'))[0];
  assert(station, 'A host station is needed');
  const path = '/stations/' + station.id + '/weekly-hours';
  const original = await request(path);
  const start = new Date(Date.now() + 5 * 86400000);
  start.setUTCHours(11,0,0,0);
  const end = new Date(start.getTime() + 3600000);
  const availabilityPath = `/stations/${station.id}/availability?startAt=${encodeURIComponent(start.toISOString())}&endAt=${encodeURIComponent(end.toISOString())}`;
  try {
    const closed = {zoneId:'Europe/Prague',days:Array.from({length:7},(_,index) => ({
      dayOfWeek:index + 1,enabled:false,opensMinute:480,closesMinute:1200
    }))};
    const saved = await request(path,host,{method:'PUT',body:JSON.stringify(closed)});
    assert.equal(saved.configured,true);
    assert.equal((await request(availabilityPath,driver)).reason,"Outside this station's weekly hours");
    const batch = await request('/stations/availability-batch',driver,{method:'POST',body:JSON.stringify({
      stationIds:[station.id],startAt:start.toISOString(),endAt:end.toISOString()
    })});
    assert.equal(batch[0].available,false);
    assert.equal(batch[0].reason,"Outside this station's weekly hours");
    const bookingResponse = await fetch(base + '/api/bookings',{
      method:'POST',headers:{'X-Demo-User':driver,'Content-Type':'application/json'},
      body:JSON.stringify({stationId:station.id,startAt:start.toISOString(),endAt:end.toISOString()})
    });
    assert.equal(bookingResponse.status,409);
    const driverResponse = await fetch(base + '/api' + path,{headers:{'X-Demo-User':driver}});
    assert.equal(driverResponse.status,403);
  } finally {
    if (original.configured) await request(path,host,{method:'PUT',body:JSON.stringify({zoneId:original.zoneId,days:original.days})});
    else await request(path,host,{method:'DELETE'});
  }
  assert.deepEqual(await request(path),original);
  console.log('Weekly hours, availability batch, authorization, and restoration passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });

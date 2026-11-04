const $ = selector => document.querySelector(selector);
const state = {
  users: [], actor: null, view: 'discover', dashboard: null, owned: [], bookings: [], saved: [],
  notices: [], pending: [], events: null, system: null, previewReadOnly: false, stations: [], map: null,
  picker: null, pickerPin: null, mapMarkers: null, focusMarker: null, selectedStation: null,
  country: 'CZ', place: 1, city: '', connector: '', mapRequest: 0, mapTotal: 0,
  clusters: [], cachedTiles: 0, sidebarOpen: false, availabilityRequest: 0,
  adminCatalog: {country:'', status:'', ownerKind:'', query:'', page:0, size:20, result:null}, catalogRequest:0,
  bookingPager: {status:'', country:'', page:0, size:8, result:null}, bookingRequest:0,
  scheduleStation: null, timeFilter: null, availableCount: 0, checkedCount: 0
};
const places = {
  CZ: window.CZECH_PLACES,
  US: [
    ['All United States', 39.5, -98.5, 4], ['New York', 40.7128, -74.006, 10],
    ['Los Angeles', 34.0522, -118.2437, 10], ['San Francisco', 37.7749, -122.4194, 11],
    ['Chicago', 41.8781, -87.6298, 10], ['Seattle', 47.6062, -122.3321, 10],
    ['Austin', 30.2672, -97.7431, 10]
  ]
};
const roleName = { DRIVER: 'Driver', PERSON: 'Private host', COMPANY: 'Company', PLATFORM: 'EC network', ADMIN: 'Administrator' };
const navConfig = {
  DRIVER: [['discover', 'Discover', 'compass'], ['saved', 'Saved chargers', 'heart'], ['trips', 'My trips', 'calendar'], ['inbox', 'Inbox', 'bell'], ['host', 'List a charger', 'plus']],
  PERSON: [['overview', 'Overview', 'grid'], ['stations', 'My charger', 'plug'], ['bookings', 'Reservations', 'calendar'], ['inbox', 'Inbox', 'bell']],
  COMPANY: [['fleet', 'Fleet', 'grid'], ['bookings', 'Reservations', 'calendar'], ['inbox', 'Inbox', 'bell']],
  PLATFORM: [['network', 'Network', 'grid'], ['stations', 'Stations', 'plug'], ['bookings', 'Reservations', 'calendar'], ['inbox', 'Inbox', 'bell']],
  ADMIN: [['control', 'Overview', 'grid'], ['catalog', 'All stations', 'plug'], ['reviews', 'Review queue', 'check'], ['bookings', 'Reservations', 'calendar'], ['inbox', 'Inbox', 'bell']]
};
const icons = {
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5 5-2Z"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  plug: '<path d="M8 3v5M16 3v5M6 8h12v3a6 6 0 0 1-6 6v4M12 17a6 6 0 0 1-6-6V8"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  bolt: '<path d="m13 2-9 11h7l-1 9 10-12h-7V2Z"/>',
  pin: '<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  filter: '<path d="M4 7h16M7 12h10M10 17h4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  chart: '<path d="M4 20V9m5 11V4m5 16v-7m5 7V7"/>',
  power: '<path d="M12 2v9M6 5a9 9 0 1 0 12 0"/>',
  heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>'
};
const svg = (name, size = 20) => `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.bolt}</svg>`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const money = (cents, country = 'CZ') => new Intl.NumberFormat('en-US', {style:'currency', currency: country === 'US' ? 'USD' : 'CZK', maximumFractionDigits:0}).format(cents / 100);
const compactCount = count => new Intl.NumberFormat('en-US', {notation:'compact', maximumFractionDigits: count < 1000 ? 0 : 1}).format(count);
const fullDate = value => new Intl.DateTimeFormat('en-US', {month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'}).format(new Date(value));
const directionsUrl = (address, city, country, latitude, longitude) => 'https://www.google.com/maps/dir/?api=1&destination=' + encodeURIComponent(
  Number.isFinite(latitude) && Number.isFinite(longitude)
    ? `${latitude},${longitude}` : `${address}, ${city}, ${country === 'US' ? 'United States' : 'Czechia'}`);
const savedId = id => state.saved.some(station => station.id === id);
const firstName = name => String(name || '').split(/[ ·]/)[0];
let toastTimer, mapTimer, filterTimer, pickerTimer, catalogTimer;

async function api(path, options = {}) {
  if (state.previewReadOnly && options.method && !['GET','HEAD'].includes(options.method.toUpperCase())
      && !(options.method.toUpperCase() === 'POST' && path === '/stations/availability-batch')) {
    throw new Error('This public preview is view-only. Changes are disabled.');
  }
  const response = await fetch('/api' + path, {
    ...options,
    headers: {'Content-Type':'application/json', 'X-Demo-User': state.actor?.id || '', ...(options.headers || {})}
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || 'Request failed (' + response.status + ')');
  return body;
}
function toast(message, tone = 'normal') {
  const box = $('#toast');
  box.textContent = message; box.dataset.tone = tone; box.classList.add('visible');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => box.classList.remove('visible'), 4600);
}
function empty(iconName, title, copy, action = '') {
  return `<div class="empty-state"><span class="empty-icon">${svg(iconName, 25)}</span><h3>${title}</h3><p>${copy}</p>${action}</div>`;
}
function metric(label, value, note = '', theme = '') {
  return `<div class="metric ${theme}"><span>${label}</span><strong>${value}</strong>${note ? `<small>${note}</small>` : ''}</div>`;
}
function pageHeading(kicker, title, copy, action = '') {
  return `<div class="page-heading"><div><span class="kicker">${kicker}</span><h1>${title}</h1><p>${copy}</p></div>${action}</div>`;
}
function pageButton(label, iconName, attrs = '') {
  return `<button type="button" class="button button-primary" ${attrs}>${svg(iconName, 18)}<span>${label}</span></button>`;
}
function navLabel() {
  const item = (navConfig[state.actor?.kind] || []).find(entry => entry[0] === state.view);
  return item?.[1] || 'Overview';
}
function renderChrome() {
  const kind = state.actor.kind;
  document.body.className = 'role-' + kind.toLowerCase() + (state.sidebarOpen ? ' sidebar-open' : '')
    + (state.previewReadOnly ? ' public-preview' : '');
  $('#preview-badge').hidden = !state.previewReadOnly;
  $('#actor').innerHTML = state.users.map(user => `<option value="${user.id}">${esc(user.name)} · ${roleName[user.kind]}</option>`).join('');
  $('#actor').value = state.actor.id;
  $('#account-avatar').textContent = firstName(state.actor.name).charAt(0).toUpperCase();
  $('#breadcrumb-space').textContent = kind === 'DRIVER' ? 'Driver space' : kind === 'ADMIN' ? 'Administration' : kind === 'PERSON' ? 'Host space' : kind === 'COMPANY' ? 'Company space' : 'EC operations';
  $('#breadcrumb-view').textContent = navLabel();
  $('#sidebar-context').innerHTML = `<div class="context-avatar">${firstName(state.actor.name).charAt(0).toUpperCase()}</div><div><small>${roleName[kind]}</small><strong>${esc(state.actor.name)}</strong></div>`;
  $('#side-nav').innerHTML = navConfig[kind].filter(([key]) => !state.previewReadOnly || key !== 'host').map(([key, label, iconName]) =>
    `<button type="button" class="nav-item ${state.view === key ? 'active' : ''}" data-view="${key}">${svg(iconName, 19)}<span>${label}</span>${key === 'inbox' && state.notices.filter(n => !n.read).length ? `<i>${state.notices.filter(n => !n.read).length}</i>` : key === 'saved' && state.saved.length ? `<i>${state.saved.length}</i>` : ''}</button>`
  ).join('');
  $('#notification-count').textContent = state.notices.filter(n => !n.read).length || '';
  const healthy = state.system?.primary === 'online' && state.system?.replica === 'streaming' && state.system?.redis === 'online';
  $('#connection-title').textContent = healthy ? 'All systems online' : 'Services connecting';
  $('#connection-subtitle').textContent = healthy ? 'Primary · replica · cache' : 'Waiting for local services';
  $('#connection-dot').classList.toggle('offline', !healthy);
}
async function loadActorData() {
  const current = state.actor;
  const [dashboard, bookings, notices, owned, pending, events, saved] = await Promise.all([
    api('/dashboard'), current.kind === 'ADMIN' ? Promise.resolve([]) : api('/bookings'), api('/notifications'),
    ['DRIVER','ADMIN'].includes(current.kind) ? Promise.resolve([]) : api('/my-stations'),
    current.kind === 'ADMIN' ? api('/admin/stations/pending') : Promise.resolve([]),
    current.kind === 'ADMIN' ? api('/events/preview') : Promise.resolve(null),
    current.kind === 'DRIVER' ? api('/saved-stations') : Promise.resolve([])
  ]);
  if (state.actor.id !== current.id) return false;
  Object.assign(state, {dashboard, bookings, notices, owned, pending, events, saved});
  return true;
}
async function setActor(id) {
  const user = state.users.find(item => item.id === id);
  if (!user) return;
  state.actor = user;
  state.view = navConfig[user.kind][0][0];
  state.bookingPager = {status:'', country:'', page:0, size:8, result:null};
  state.sidebarOpen = false;
  localStorage.setItem('ec-demo-actor', id);
  try { if (await loadActorData()) render(); }
  catch (error) { toast(error.message, 'error'); }
}
function selectView(view) {
  if (state.previewReadOnly && view === 'host') { toast('Profile creation is disabled in this view-only demo.'); return; }
  if (view === 'host') { $('#new-account-kind').value = 'PERSON'; window.refreshCustomControls?.(); $('#account-dialog').showModal(); return; }
  if (!navConfig[state.actor.kind].some(item => item[0] === view)) return;
  state.view = view; state.sidebarOpen = false; render();
  window.scrollTo({top:0, behavior:'instant'});
}
function destroyMap() {
  state.mapRequest++;
  clearTimeout(mapTimer);
  if (state.map) { state.map.off(); state.map.remove(); state.map = null; state.mapMarkers = null; state.focusMarker = null; }
}
function clearFocus() {
  if (state.focusMarker && state.map) state.map.removeLayer(state.focusMarker);
  state.focusMarker = null;
}
function moveMapTo(place) {
  if (!state.map) return;
  clearFocus();
  state.map.stop();
  state.map.setView([place[1], place[2]], place[3], {animate:false});
}
function render() {
  destroyMap();
  renderChrome();
  const kind = state.actor.kind;
  const content = kind === 'DRIVER' ? (state.view === 'discover' ? renderExplore() : state.view === 'saved' ? renderSaved() : state.view === 'trips' ? renderReservations(true) : renderInbox())
    : kind === 'PERSON' ? (state.view === 'overview' ? renderHostOverview() : state.view === 'stations' ? renderStationsPage('host') : state.view === 'bookings' ? renderReservations(false) : renderInbox())
    : kind === 'COMPANY' ? (state.view === 'fleet' ? renderFleet() : state.view === 'bookings' ? renderReservations(false) : renderInbox())
    : kind === 'PLATFORM' ? (state.view === 'network' ? renderNetwork() : state.view === 'stations' ? renderStationsPage('network') : state.view === 'bookings' ? renderReservations(false) : renderInbox())
    : (state.view === 'control' ? renderAdmin() : state.view === 'catalog' ? renderAdminCatalog() : state.view === 'reviews' ? renderReviews() : state.view === 'bookings' ? renderReservations(false) : renderInbox());
  $('#main-content').innerHTML = content;
  if (kind === 'DRIVER' && state.view === 'discover') mountMap();
  if (kind === 'ADMIN' && state.view === 'catalog') loadAdminCatalog();
  if (state.view === 'trips' || state.view === 'bookings') loadBookingPage();
}

function renderExplore() {
  const placeOptions = places[state.country].map((place, index) => `<option value="${index}" ${index === state.place ? 'selected' : ''}>${place[0]}</option>`).join('');
  const cityOptions = places[state.country].slice(1).map(place => `<option value="${esc(place[0])}"></option>`).join('');
  return `<section class="view discover-view">
    ${pageHeading('Explore charging', 'Find your next charge.', state.previewReadOnly
      ? 'Explore availability across private, company, and EC chargers. This public preview does not create reservations.'
      : 'Find a charger from a private host, a company, or the EC network. Reserve a time that works for you.')}
    <div class="explore-toolbar">
      <label><span>Country</span><select id="country-filter"><option value="CZ" ${state.country === 'CZ' ? 'selected' : ''}>Czechia</option><option value="US" ${state.country === 'US' ? 'selected' : ''}>United States</option></select></label>
      <label><span>Explore near</span><select id="place-filter">${placeOptions}</select></label>
      <label class="city-search"><span>City or town</span><input id="city-filter" type="search" list="city-options" value="${esc(state.city)}" placeholder="Type a place name" autocomplete="off"><datalist id="city-options">${cityOptions}</datalist></label>
      <label><span>Connector</span><select id="connector-filter"><option value="" ${!state.connector ? 'selected' : ''}>Any connector</option><option value="Type 2" ${state.connector === 'Type 2' ? 'selected' : ''}>Type 2</option><option value="CCS2" ${state.connector === 'CCS2' ? 'selected' : ''}>CCS2</option></select></label>
    </div>
    <div class="explore-layout">
      <div class="map-panel"><div id="explore-map" role="application" aria-label="Interactive map of charging stations"></div>
        <div class="map-location">${svg('layers', 16)}<span id="map-location-label">${places[state.country][state.place][0]}</span></div>
        <div class="map-hint">Numbers show chargers · click to explore</div>
      </div>
      <div class="result-panel">
        <div class="result-heading"><div><span class="result-overline">${state.timeFilter ? 'Available for your time' : 'Stations in view'}</span><h2 id="result-count">Loading locations...</h2></div><button type="button" class="time-filter-button ${state.timeFilter ? 'active' : ''}" data-time-search title="Search by arrival time">${svg('clock', 16)}<span>${state.timeFilter ? 'Change time' : 'Choose time'}</span></button></div>
        <div id="time-filter-summary" class="time-filter-summary" ${state.timeFilter ? '' : 'hidden'}>${state.timeFilter ? `${svg('calendar',15)}<span>${esc(searchTimeLabel())}</span><button type="button" data-clear-time aria-label="Clear time search">×</button>` : ''}</div>
        <div id="station-results" class="result-list"><div class="loading-list"><span></span><span></span><span></span></div></div>
        <div class="result-footer" id="result-footer">${state.timeFilter ? 'List checks the nearest 100 chargers. Map markers show all stations.' : state.previewReadOnly ? 'Sample locations · view-only public demo.' : 'Fictional stations · reservations work locally.'}</div>
      </div>
    </div>
    <div class="explore-bottom"><span>${svg('check', 18)} ${state.previewReadOnly ? 'Check a time without changing the schedule.' : 'A slot is held as soon as you confirm it.'}</span><button type="button" class="subtle-link" data-view="trips">View my trips ${svg('arrow', 16)}</button></div>
  </section>`;
}
function stationCard(station) {
  const ownership = station.ownerKind === 'PERSON' ? 'Private host' : station.ownerKind === 'COMPANY' ? 'Company' : 'EC network';
  return `<article class="result-card" data-focus="${station.id}" tabindex="0">
    <div class="result-symbol ${station.ownerKind.toLowerCase()}">${svg('bolt', 22)}</div>
    <div class="result-main"><div class="result-title-row"><h3>${esc(station.name)}</h3><div class="result-title-tools"><span class="result-power">${station.powerKw} kW</span><button type="button" class="save-button ${savedId(station.id) ? 'is-saved' : ''}" data-save="${station.id}" aria-label="${savedId(station.id) ? 'Remove' : 'Save'} ${esc(station.name)}" title="${savedId(station.id) ? 'Remove from saved chargers' : 'Save charger'}">${svg('heart',16)}</button></div></div>
      <p>${esc(station.city)} · ${esc(station.address)}</p>
      <div class="result-tags"><span>${esc(station.connector)}</span><span>${ownership}</span>${station.synthetic ? '<span>Sample location</span>' : ''}</div>
    </div>
    <div class="result-action"><strong>${money(station.pricePerHourCents, station.countryCode)}<small> / hour</small></strong>
      <button type="button" data-book="${station.id}" class="reserve-button">${state.previewReadOnly ? 'Check slot' : 'Reserve'} ${svg('arrow', 15)}</button></div>
  </article>`;
}
function savedStationCard(station) {
  const available = station.active && station.listingStatus === 'APPROVED';
  const ownership = station.ownerKind === 'PERSON' ? 'Private host' : station.ownerKind === 'COMPANY' ? 'Company' : 'EC network';
  return `<article class="saved-card">
    <div class="saved-card-top"><span class="saved-card-icon ${station.ownerKind.toLowerCase()}">${svg('bolt',22)}</span><span class="saved-card-type">${ownership}</span>
      <button type="button" class="save-button is-saved" data-save="${station.id}" aria-label="Remove ${esc(station.name)} from saved chargers" title="Remove from saved chargers">${svg('heart',18)}</button></div>
    <h2>${esc(station.name)}</h2><p>${svg('pin',16)} ${esc(station.address)}, ${esc(station.city)}</p>
    <div class="saved-card-specs"><span>${station.powerKw} kW</span><span>${esc(station.connector)}</span><span>${station.countryCode === 'US' ? 'United States' : 'Czechia'}</span></div>
    <div class="saved-card-bottom"><div><small>From</small><strong>${money(station.pricePerHourCents,station.countryCode)} <em>/ hour</em></strong></div>
      <div class="saved-card-actions"><a class="button button-outline" href="${esc(directionsUrl(station.address,station.city,station.countryCode,station.latitude,station.longitude))}" target="_blank" rel="noopener" aria-label="Directions to ${esc(station.name)} in Google Maps">${svg('pin',16)} Directions</a>
      ${available ? `<button type="button" class="button button-primary" data-book="${station.id}">${state.previewReadOnly ? 'Check slot' : 'Reserve'} ${svg('arrow',16)}</button>` : '<span class="saved-unavailable">Currently unavailable</span>'}</div></div>
  </article>`;
}
function renderSaved() {
  return `<section class="view saved-view">
    <div class="saved-top"><div><span class="kicker">${state.saved.length} ${state.saved.length === 1 ? 'charger' : 'chargers'} saved</span><h1>Saved chargers</h1><p>Places you can return to without searching the map again.</p></div>
      <button type="button" class="button button-outline" data-view="discover">Explore the map ${svg('arrow',17)}</button></div>
    ${state.saved.length ? `<div class="saved-grid">${state.saved.map(savedStationCard).join('')}</div>` : empty('heart','No saved chargers yet','Explore the map and tap the heart on a station you want to find again.',pageButton('Explore chargers','compass','data-view="discover"'))}
  </section>`;
}
function renderResults() {
  const count = $('#result-count'), list = $('#station-results');
  if (!count || !list) return;
  count.textContent = state.timeFilter ? `${state.availableCount} of ${state.checkedCount} open` : state.mapTotal.toLocaleString('en-US') + ' nearby';
  list.innerHTML = state.stations.length ? state.stations.map(stationCard).join('')
    : state.timeFilter ? empty('clock', 'No open slots in this area', 'Try another arrival time or move the map. We checked the nearest 100 chargers in view.')
    : empty('pin', 'No chargers here yet', 'Move the map or change your filters to discover more locations.');
}
function searchTimeLabel() {
  if (!state.timeFilter) return '';
  return new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(state.timeFilter.startAt))
    + ` · ${state.timeFilter.durationMinutes < 60 ? state.timeFilter.durationMinutes + ' min' : state.timeFilter.durationMinutes / 60 + ' hr'}`;
}
function syncTimeFilter() {
  const overline = $('.result-overline'), button = $('.time-filter-button'), summary = $('#time-filter-summary'), footer = $('#result-footer');
  if (!overline || !button || !summary || !footer) return;
  overline.textContent = state.timeFilter ? 'Available for your time' : 'Stations in view';
  button.classList.toggle('active', !!state.timeFilter);
  button.querySelector('span').textContent = state.timeFilter ? 'Change time' : 'Choose time';
  summary.hidden = !state.timeFilter;
  summary.innerHTML = state.timeFilter ? `${svg('calendar',15)}<span>${esc(searchTimeLabel())}</span><button type="button" data-clear-time aria-label="Clear time search">×</button>` : '';
  footer.textContent = state.timeFilter ? 'List checks the nearest 100 chargers. Map markers show all stations.' : state.previewReadOnly ? 'Sample locations · view-only public demo.' : 'Fictional stations · reservations work locally.';
}
function openTimeSearch() {
  const start = state.timeFilter ? new Date(state.timeFilter.startAt) : new Date(Date.now() + 2 * 3600000);
  if (!state.timeFilter) start.setMinutes(0,0,0);
  $('#search-start-at').value = localInput(start);
  $('#search-duration').value = String(state.timeFilter?.durationMinutes || 60);
  window.refreshCustomControls?.();
  $('#time-search-dialog').showModal();
}
function submitTimeSearch(event) {
  event.preventDefault();
  const start = new Date($('#search-start-at').value), durationMinutes = Number($('#search-duration').value);
  if (Number.isNaN(+start) || start <= new Date() || ![30,60,90,120,180,240].includes(durationMinutes)) {
    toast('Choose a future arrival and a charging time up to 4 hours.','error'); return;
  }
  state.timeFilter = {startAt:start.toISOString(), durationMinutes};
  $('#time-search-dialog').close();
  syncTimeFilter(); queryMap();
}
function mergeClusters(clusters) {
  const merged = [];
  const separation = state.map.getZoom() <= 8 ? 72
    : state.map.getZoom() >= 16 ? 55
    : state.map.getZoom() >= 14 || state.mapTotal <= 1000 ? 76 : 102;
  for (const cluster of [...clusters].sort((a,b) => b.count - a.count)) {
    const pixel = state.map.latLngToContainerPoint([cluster.latitude, cluster.longitude]);
    let match = merged.find(item => {
      const point = state.map.latLngToContainerPoint([item.latitude, item.longitude]);
      return Math.hypot(pixel.x - point.x, pixel.y - point.y) < separation;
    });
    if (!match) {
      merged.push({...cluster});
    } else {
      const total = match.count + cluster.count;
      match.latitude = (match.latitude * match.count + cluster.latitude * cluster.count) / total;
      match.longitude = (match.longitude * match.count + cluster.longitude * cluster.count) / total;
      match.count = total;
      match.stationId = null;
      match.minPriceCents = Math.min(match.minPriceCents, cluster.minPriceCents);
    }
  }
  return merged;
}
function normalizePlace(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}
function exactPlace(country, query) {
  const text = normalizePlace(query);
  if (!text) return null;
  const index = places[country].findIndex((place, i) => i > 0 &&
    (normalizePlace(place[0]) === text || normalizePlace(place[4]) === text));
  return index < 0 ? null : {index, place: places[country][index]};
}
function renderMapMarkers() {
  if (!state.mapMarkers) return;
  state.mapMarkers.clearLayers();
  for (const cluster of mergeClusters(state.clusters)) {
    const single = cluster.count === 1 && cluster.stationId;
    const amount = Math.round(cluster.minPriceCents / 100);
    const label = single ? (state.country === 'US' ? '$' + amount : amount + ' Kč') : compactCount(cluster.count);
    const density = cluster.count >= 500 ? 'dense' : cluster.count >= 50 ? 'medium' : 'light';
    const content = single
      ? `<span class="map-pin map-pin-price"><span class="map-pin-bolt">ϟ</span><strong>${label}</strong></span>`
      : `<span class="map-pin map-pin-cluster ${density}" aria-label="${cluster.count} chargers"><strong>${label}</strong></span>`;
    const diameter = cluster.count >= 500 ? 50 : cluster.count >= 50 ? 46 : 42;
    const pixel = state.map.latLngToContainerPoint([cluster.latitude, cluster.longitude]);
    const size = state.map.getSize();
    const inset = 44;
    const shownAt = state.map.containerPointToLatLng([
      Math.max(inset, Math.min(size.x - inset, pixel.x)),
      Math.max(inset, Math.min(size.y - inset, pixel.y))
    ]);
    const marker = L.marker(shownAt, {
      icon: L.divIcon({className:'map-marker-wrap', html:content,
        iconSize:single ? [82,38] : [diameter,diameter],
        iconAnchor:single ? [41,19] : [diameter/2,diameter/2]}),
      keyboard: true
    });
    marker.on('click', () => {
      if (single) return openBooking(cluster.stationId);
      clearFocus();
      state.map.stop();
      state.map.setView([cluster.latitude, cluster.longitude], Math.min(18, state.map.getZoom() + 2), {animate:false});
    });
    state.mapMarkers.addLayer(marker);
  }
}
function focusStation(station) {
  if (!state.map) return;
  clearFocus();
  const point = [station.latitude, station.longitude];
  state.map.stop();
  state.map.setView(point, Math.max(15, state.map.getZoom()), {animate:false});
  const content = document.createElement('div');
  content.className = 'map-popup';
  content.innerHTML = `<strong>${esc(station.name)}</strong><small>${esc(station.address)}, ${esc(station.city)}</small><span>${station.powerKw} kW · ${money(station.pricePerHourCents, station.countryCode)} / hour</span>`;
  const button = document.createElement('button');
  button.type = 'button'; button.textContent = state.previewReadOnly ? 'Check availability' : 'Reserve this charger';
  button.addEventListener('click', () => openBooking(station.id));
  content.append(button);
  const saveButton = document.createElement('button');
  saveButton.type = 'button'; saveButton.className = 'popup-save'; saveButton.dataset.save = station.id;
  saveButton.textContent = savedId(station.id) ? 'Remove from saved' : 'Save for later';
  content.append(saveButton);
  state.focusMarker = L.marker(point, {
    icon:L.divIcon({className:'focus-marker',html:'<span>ϟ</span>',iconSize:[38,43],iconAnchor:[19,40]}),
    zIndexOffset:1000
  }).addTo(state.map).bindPopup(content,{offset:[0,-31],minWidth:190}).openPopup();
}
async function queryMap(consistent = false) {
  if (!state.map || state.view !== 'discover' || state.actor.kind !== 'DRIVER') return;
  if (state.timeFilter && new Date(state.timeFilter.startAt) <= new Date()) {
    state.timeFilter = null; syncTimeFilter();
  }
  const request = ++state.mapRequest, bounds = state.map.getBounds();
  const params = new URLSearchParams({
    country: state.country, west: Math.max(-180,bounds.getWest()).toFixed(5),
    south: Math.max(-85,bounds.getSouth()).toFixed(5),
    east: Math.min(180,bounds.getEast()).toFixed(5),
    north: Math.min(85,bounds.getNorth()).toFixed(5), zoom: state.map.getZoom(),
    city: state.city.trim(), connector: state.connector, limit: state.timeFilter ? '100' : '24', consistent: String(consistent)
  });
  try {
    const data = await api('/map/explore?' + params);
    if (request !== state.mapRequest || !state.map) return;
    let visible = data.stations;
    state.availableCount = 0;
    state.checkedCount = visible.length;
    if (state.timeFilter && visible.length) {
      const start = new Date(state.timeFilter.startAt);
      const end = new Date(start.getTime() + state.timeFilter.durationMinutes * 60000);
      const checks = await api('/stations/availability-batch', {method:'POST',body:JSON.stringify({
        stationIds:visible.map(station => station.id), startAt:start.toISOString(), endAt:end.toISOString()
      })});
      if (request !== state.mapRequest || !state.map) return;
      const open = new Set(checks.filter(check => check.available).map(check => check.stationId));
      visible = visible.filter(station => open.has(station.id));
      state.availableCount = visible.length;
      visible = visible.slice(0,24);
    }
    state.stations = visible; state.clusters = data.clusters;
    state.mapTotal = data.total; state.cachedTiles = data.cachedTiles;
    renderResults(); renderMapMarkers();
  } catch (error) {
    if (request === state.mapRequest) {
      const count = $('#result-count'), list = $('#station-results');
      if (count) count.textContent = 'Search unavailable';
      if (list) list.innerHTML = empty('pin', 'Try a closer view', esc(error.message));
    }
  }
}
function queueMapSearch() { clearTimeout(mapTimer); mapTimer = setTimeout(() => queryMap(), 230); }
function mountMap() {
  const el = $('#explore-map');
  if (!el) return;
  const place = places[state.country][state.place];
  state.map = L.map(el, {zoomControl:false, minZoom:3, maxZoom:18, preferCanvas:true}).setView([place[1],place[2]],place[3]);
  L.control.zoom({position:'bottomleft'}).addTo(state.map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom:18, attribution:'&copy; OpenStreetMap contributors'
  }).addTo(state.map);
  fetch('/vendor/countries.geojson').then(result => result.json())
    .then(geo => { if (state.map) L.geoJSON(geo, {interactive:false, style:{color:'#7896a8',weight:1,fillOpacity:0}}).addTo(state.map); })
    .catch(() => {});
  state.mapMarkers = L.layerGroup().addTo(state.map);
  state.map.on('moveend', queueMapSearch);
  state.map.on('dragstart', clearFocus);
  setTimeout(() => { if (state.map) { state.map.invalidateSize(); queryMap(); } }, 100);
}

function dashboardMetrics(start = 0, end = undefined) {
  return state.dashboard.metrics.slice(start, end).map(item =>
    metric(esc(item.label), item.format === 'money' ? money(item.value, item.countryCode) : item.value.toLocaleString('en-US'),
      item.simulated ? 'Calculated preview' : 'Live local data')
  ).join('');
}
function listingBadge(station) {
  const status = !station.active ? 'Paused' : station.listingStatus === 'PENDING' ? 'In review'
    : station.listingStatus === 'REJECTED' ? 'Declined' : 'Live';
  return `<span class="listing-badge ${status.toLowerCase().replace(' ','-')}"><i></i>${status}</span>`;
}
function stationActions(station) {
  return `<div class="station-actions"><button type="button" class="text-action" data-telemetry="${station.id}">${svg('chart', 17)} Telemetry</button>
    <button type="button" class="text-action" data-schedule="${station.id}">${svg('calendar', 17)} Schedule</button>
    <button type="button" class="text-action" data-toggle="${station.id}" data-active="${station.active}">${svg('power', 17)} ${station.active ? 'Pause' : 'Resume'}</button></div>`;
}
function renderHostOverview() {
  const station = state.owned[0];
  const income = state.dashboard.metrics.find(item => item.countryCode === 'CZ')?.value || 0;
  return `<section class="view host-view">
    <div class="host-hero">
      <div class="host-hero-copy"><span class="hero-chip">${svg('pin', 15)} Private hosting</span>
        <h1>Your charger,<br>on your schedule.</h1>
        <p>${state.previewReadOnly ? 'Explore opening hours and see the drivers who booked this sample charger.' : 'Set weekly hours, block dates, and keep track of the drivers who booked.'}</p>
        ${pageButton(station ? 'Set opening hours' : 'Add my first charger', station ? 'calendar' : 'plus', station ? `data-schedule="${station.id}"` : 'data-add-station')}
      </div>
      <div class="charger-illustration" aria-hidden="true"><span class="art-line art-line-one"></span><span class="art-line art-line-two"></span><span class="charger-body"><span class="charger-screen"><b>ϟ</b><i></i><i></i></span><span class="charger-slot"></span></span><span class="charger-cable"></span><span class="art-caption">POWER SHARED / 01</span></div>
    </div>
    <div class="host-overview-grid">
      <div class="host-spotlight"><div class="section-inline-head"><div><span class="kicker">Your place</span><h2>${station ? esc(station.name) : 'A charger that earns'}</h2></div>${station ? listingBadge(station) : ''}</div>
        ${station ? `<p>${esc(station.address)}, ${esc(station.city)}</p><div class="spotlight-facts"><span>${svg('bolt',18)} ${station.powerKw} kW</span><span>${esc(station.connector)}</span><span>${money(station.pricePerHourCents,station.countryCode)} / hour</span></div>${stationActions(station)}`
          : `<p>There is no charger on your profile yet. Add one and the EC team will review it before it appears on the map.</p><button class="button button-outline" type="button" data-add-station>${svg('plus',18)} Add a charger</button>`}
      </div>
      <div class="host-earnings"><span class="kicker">At a glance</span><div class="earnings-number">${money(income, 'CZ')}</div><p>Estimated payout from confirmed reservations in Czechia. Payments remain simulated in this preview.</p><div class="earnings-rule"><span>Platform commission</span><strong>12%</strong></div></div>
    </div>
    <div class="recent-panel"><div class="section-inline-head"><div><span class="kicker">Activity</span><h2>People charging with you</h2></div><button class="subtle-link" data-view="bookings">All reservations ${svg('arrow',16)}</button></div>
      ${state.bookings.length ? state.bookings.slice(0,3).map(bookingRow).join('') : empty('calendar','No reservations yet','Your bookings will appear here as soon as a driver reserves a slot.')}</div>
  </section>`;
}
function ownedStationCard(station) {
  return `<article class="owned-card"><div class="owned-card-top"><div class="owned-icon">${svg('bolt',25)}</div>${listingBadge(station)}</div>
    <h3>${esc(station.name)}</h3><p>${esc(station.address)}, ${esc(station.city)}</p>
    <div class="owned-specs"><span>${station.powerKw} kW</span><span>${esc(station.connector)}</span><span>${money(station.pricePerHourCents, station.countryCode)} / h</span></div>
    ${stationActions(station)}</article>`;
}
function renderStationsPage(flavor) {
  const host = flavor === 'host';
  return `<section class="view owned-view">
    ${pageHeading(host ? 'Your home charger' : 'EC network', host ? 'Your charger, your rules.' : 'Stations that move cities.', state.previewReadOnly ? 'Explore station details, opening hours, and listing status.' : host ? 'Set availability and keep your listing ready for nearby drivers.' : 'Operate EC-owned charging points across the network.',
      pageButton('Add station','plus','data-add-station'))}
    <div class="owned-intro"><div><strong>${state.owned.length} ${state.owned.length === 1 ? 'station' : 'stations'}</strong><span>in your workspace</span></div><div><strong>${state.owned.filter(s => s.active && s.listingStatus === 'APPROVED').length}</strong><span>open for drivers</span></div><div><strong>${state.owned.filter(s => s.listingStatus === 'PENDING').length}</strong><span>awaiting review</span></div></div>
    <div class="owned-grid">${state.owned.length ? state.owned.map(ownedStationCard).join('') : empty('plug','Your network starts here','Add a station to make your first charging spot available.',pageButton('Add station','plus','data-add-station'))}</div>
    <div class="help-strip">${svg('check',19)} <span>Access instructions are only shared with drivers after a confirmed reservation.</span></div>
  </section>`;
}
function fleetTable() {
  return state.owned.length ? `<div class="fleet-table"><div class="fleet-table-head"><span>Station</span><span>Location</span><span>Power</span><span>Hourly rate</span><span>Status</span><span>Controls</span></div>
    ${state.owned.map(station => `<div class="fleet-row"><div class="fleet-name"><span class="fleet-icon">${svg('bolt',19)}</span><div><strong>${esc(station.name)}</strong><small>${esc(station.connector)}</small></div></div>
      <span>${esc(station.city)} <small>${station.countryCode}</small></span><strong>${station.powerKw} kW</strong><strong>${money(station.pricePerHourCents,station.countryCode)}</strong>
      ${listingBadge(station)}${stationActions(station)}</div>`).join('')}</div>`
    : empty('plug','No stations in your fleet','Add your first location to start managing it here.',pageButton('Add station','plus','data-add-station'));
}
function renderFleet() {
  const active = state.owned.some(station => station.active);
  return `<section class="view fleet-view">
    ${pageHeading(esc(state.actor.name) + ' operations', 'Every plug, one view.', state.previewReadOnly ? 'Explore your stations, schedules, and incoming reservations from one place.' : 'Manage your stations, availability, and incoming reservations from one place.', pageButton('Add station','plus','data-add-station'))}
    <div class="fleet-summary"><div class="fleet-summary-intro">${svg('layers',30)}<strong>${state.owned.length}</strong><span>stations in your fleet</span></div>
      <div class="fleet-summary-stats">${dashboardMetrics(1,4)}</div></div>
    <div class="section-inline-head fleet-section-head"><div><span class="kicker">Fleet directory</span><h2>Your charging locations</h2></div>
      ${state.owned.length ? `<button type="button" class="button button-outline" data-fleet="${!active}">${svg('power',17)} ${active ? 'Pause all' : 'Resume all'}</button>` : ''}</div>
    ${fleetTable()}
    <div class="fleet-bottom"><div><span class="kicker">Partner earnings</span><h3>Payouts are estimates</h3><p>EC keeps 12% of partner bookings. No real transfers take place in this preview.</p></div><button class="button button-light" data-view="bookings">View reservations ${svg('arrow',17)}</button></div>
  </section>`;
}
function renderNetwork() {
  const active = state.owned.some(station => station.active);
  return `<section class="view network-view">
    <div class="network-hero"><div><span class="hero-chip">EC owned network</span><h1>Power where<br>people move.</h1><p>${state.previewReadOnly ? 'Explore EC stations from neighborhood plugs to high-power hubs.' : 'Keep every EC station ready, from a neighborhood stop to a high-power hub.'}</p>
      ${pageButton('Add an EC station','plus','data-add-station')}</div><div class="network-orbit" aria-hidden="true"><span>ϟ</span><i></i><i></i><i></i></div></div>
    <div class="network-metrics">${dashboardMetrics()}</div>
    <div class="section-inline-head"><div><span class="kicker">Live directory</span><h2>EC stations</h2></div>
      <div class="inline-actions"><button class="button button-outline" data-view="stations">Manage stations</button>
      ${state.owned.length ? `<button class="button button-outline" data-fleet="${!active}">${active ? 'Pause network' : 'Resume network'}</button>` : ''}</div></div>
    <div class="network-stations">${state.owned.length ? state.owned.map(ownedStationCard).join('') : empty('plug','No EC stations yet','Add the first EC-owned station.',pageButton('Add station','plus','data-add-station'))}</div>
  </section>`;
}
function reviewCard(station) {
  return `<article class="review-card"><span class="review-symbol">${svg('plug',22)}</span><div><div class="review-top"><strong>${esc(station.name)}</strong><span>${station.ownerKind === 'COMPANY' ? 'Company' : 'Private host'}</span></div>
    <p>${esc(station.ownerName)} · ${esc(station.address)}, ${esc(station.city)} · ${station.countryCode}</p>
    <div class="review-specs"><span>${station.powerKw} kW</span><span>${esc(station.connector)}</span><span>${money(station.pricePerHourCents,station.countryCode)} / hour</span><span>${station.latitude.toFixed(4)}, ${station.longitude.toFixed(4)}</span></div></div>
    <div class="review-actions"><button type="button" class="button button-primary" data-decision="${station.id}" data-approve="true">Approve</button><button type="button" class="button button-outline" data-decision="${station.id}" data-approve="false">Decline</button></div></article>`;
}
function adminStatus() {
  const system = state.system || {};
  return `<div class="service-grid"><div><span class="service-led ${system.primary === 'online' ? '' : 'off'}"></span><strong>Primary database</strong><small>${system.primary === 'online' ? 'Operational' : 'Unavailable'}</small></div>
    <div><span class="service-led ${system.replica === 'streaming' ? '' : 'off'}"></span><strong>Read replica</strong><small>${system.replica === 'streaming' ? 'Streaming' : 'Unavailable'}</small></div>
    <div><span class="service-led ${system.redis === 'online' ? '' : 'off'}"></span><strong>Cluster cache</strong><small>${system.redis === 'online' ? 'Operational' : 'Unavailable'}</small></div></div>`;
}
function renderAdmin() {
  return `<section class="view admin-view">
    <div class="admin-hero"><div><span class="hero-chip">Platform operations</span><h1>Keep the network<br>moving.</h1><p>${state.previewReadOnly ? 'Inspect new locations, monitor reservations, and check service health.' : 'Review new locations, monitor reservations, and keep local services healthy.'}</p></div>
      <div class="admin-hero-stat"><span>Stations on the map</span><strong>${state.dashboard.metrics[0].value.toLocaleString('en-US')}</strong><small>Across Czechia and the US</small></div></div>
    <div class="admin-topline"><div>${svg('check',20)} <strong>${state.pending.length}</strong><span>listings to review</span></div><div>${svg('calendar',20)} <strong>${state.dashboard.metrics[2].value}</strong><span>reservations</span></div>
      <div>${svg('bell',20)} <strong>${state.notices.filter(n => !n.read).length}</strong><span>new notifications</span></div></div>
    <div class="admin-grid ${state.pending.length ? '' : 'queue-clear'}">${state.pending.length ? `<div class="admin-panel"><div class="section-inline-head"><div><span class="kicker">Moderation</span><h2>Review queue</h2></div><button class="subtle-link" data-view="reviews">Open queue ${svg('arrow',16)}</button></div>
      ${state.pending.slice(0,3).map(reviewCard).join('')}</div>` : ''}
      <div class="admin-side"><div class="admin-panel"><span class="kicker">Station operations</span><h2>Every charging point</h2><p>${state.previewReadOnly ? 'Search the full catalog and inspect simulated telemetry.' : 'Search the full catalog, inspect simulated telemetry, and control availability.'}</p><button type="button" class="button button-primary" data-view="catalog">Open station directory ${svg('arrow',16)}</button></div><div class="admin-panel"><span class="kicker">Service health</span><h2>Local infrastructure</h2>${adminStatus()}</div>
        <div class="admin-panel event-card"><span class="kicker">Event transport · demo</span><h2>Local outbox</h2><p>Booking and catalog events are processed locally. Kafka is represented by this preview stream.</p>
          <div class="event-count"><strong>${state.events?.pendingReservationEvents ?? 0}</strong><span>reservation events waiting</span></div>
          <div class="event-count"><strong>${state.events?.pendingCatalogEvents ?? 0}</strong><span>catalog events waiting</span></div></div></div></div>
  </section>`;
}
function renderReviews() {
  return `<section class="view reviews-view">
    ${pageHeading('Trust and safety', 'Review new locations.', 'Every partner station is checked before drivers can discover or reserve it.')}
    <div class="review-summary"><div><strong>${state.pending.length}</strong><span>awaiting decision</span></div><p>${state.previewReadOnly ? 'Inspect the listing details an administrator would review. Decisions are disabled in this public demo.' : 'Approve accurate listings or decline entries that need changes. Hosts receive a notification after your decision.'}</p></div>
    <div class="review-list">${state.pending.length ? state.pending.map(reviewCard).join('') : empty('check','All caught up','No stations are waiting for review right now.')}</div>
  </section>`;
}
function renderAdminCatalog() {
  const filters = state.adminCatalog;
  return `<section class="view catalog-view">
    ${pageHeading('Station operations', 'Every charger in view.', state.previewReadOnly
      ? 'Find a location, inspect its simulated pulse, and review the schedule.'
      : 'Find a location, inspect its simulated pulse, and control whether drivers can reserve it.')}
    <div class="catalog-filters">
      <label><span>Find station, city, or owner</span><input id="catalog-query" type="search" value="${esc(filters.query)}" placeholder="Search the network" autocomplete="off"></label>
      <label><span>Country</span><select id="catalog-country"><option value="">All countries</option><option value="CZ" ${filters.country === 'CZ' ? 'selected' : ''}>Czechia</option><option value="US" ${filters.country === 'US' ? 'selected' : ''}>United States</option></select></label>
      <label><span>Listing</span><select id="catalog-status"><option value="">All listings</option><option value="APPROVED" ${filters.status === 'APPROVED' ? 'selected' : ''}>Approved</option><option value="PENDING" ${filters.status === 'PENDING' ? 'selected' : ''}>In review</option><option value="REJECTED" ${filters.status === 'REJECTED' ? 'selected' : ''}>Declined</option></select></label>
      <label><span>Operator</span><select id="catalog-owner"><option value="">All operators</option><option value="PERSON" ${filters.ownerKind === 'PERSON' ? 'selected' : ''}>Private hosts</option><option value="COMPANY" ${filters.ownerKind === 'COMPANY' ? 'selected' : ''}>Companies</option><option value="PLATFORM" ${filters.ownerKind === 'PLATFORM' ? 'selected' : ''}>EC network</option></select></label>
    </div>
    <div class="catalog-heading"><div><span class="kicker">Catalog</span><h2>Charging locations</h2></div><span id="catalog-total">Loading stations…</span></div>
    <div id="catalog-results" class="catalog-results"><div class="loading-list"><span></span><span></span></div></div>
    <nav id="catalog-pagination" class="catalog-pagination" aria-label="Station pages"></nav>
  </section>`;
}
function catalogRow(station) {
  const owner = station.ownerKind === 'PERSON' ? 'Private host' : station.ownerKind === 'COMPANY' ? 'Company' : 'EC network';
  return `<article class="catalog-row"><div class="catalog-station"><span class="catalog-station-icon">${svg('bolt',19)}</span><div><strong>${esc(station.name)}</strong><small>${esc(station.address)}, ${esc(station.city)} · ${station.countryCode}</small></div></div>
    <div class="catalog-operator"><span>Operator</span><strong>${esc(station.ownerName)}</strong><small>${owner}${station.synthetic ? ' · Sample location' : ''}</small></div>
    <div class="catalog-spec"><span>Connector</span><strong>${esc(station.connector)} · ${station.powerKw} kW</strong><small>${money(station.pricePerHourCents, station.countryCode)} / hour</small></div>
    ${listingBadge(station)}<div class="catalog-actions"><button type="button" class="text-action" data-telemetry="${station.id}">${svg('chart',16)} Telemetry</button><button type="button" class="text-action" data-schedule="${station.id}">${svg('calendar',16)} Schedule</button><button type="button" class="text-action" data-toggle="${station.id}" data-active="${station.active}">${svg('power',16)} ${station.active ? 'Pause' : 'Resume'}</button></div></article>`;
}
async function loadAdminCatalog() {
  if (state.actor?.kind !== 'ADMIN' || state.view !== 'catalog') return;
  const request = ++state.catalogRequest;
  const filters = state.adminCatalog;
  const params = new URLSearchParams({country:filters.country,status:filters.status,ownerKind:filters.ownerKind,
    query:filters.query,page:String(filters.page),size:String(filters.size)});
  const results = $('#catalog-results');
  if (results) results.innerHTML = '<div class="catalog-loading">Finding stations…</div>';
  try {
    const page = await api('/admin/stations?' + params);
    if (request !== state.catalogRequest || state.view !== 'catalog') return;
    filters.result = page;
    $('#catalog-total').textContent = page.total.toLocaleString('en-US') + ' stations';
    $('#catalog-results').innerHTML = page.items.length ? page.items.map(catalogRow).join('')
      : empty('plug','No stations found','Try another city, operator, or status.');
    const pagination = $('#catalog-pagination');
    if (page.pages <= 1) { pagination.innerHTML = ''; return; }
    const from = Math.max(0, Math.min(page.page - 2, page.pages - 5));
    const to = Math.min(page.pages, from + 5);
    pagination.innerHTML = `<button type="button" data-catalog-page="${page.page - 1}" ${page.page === 0 ? 'disabled' : ''}>Previous</button>
      ${Array.from({length:to-from},(_,i) => from+i).map(number => `<button type="button" data-catalog-page="${number}" ${number === page.page ? 'aria-current="page"' : ''}>${number+1}</button>`).join('')}
      <button type="button" data-catalog-page="${page.page + 1}" ${page.page >= page.pages - 1 ? 'disabled' : ''}>Next</button><span>Page ${page.page+1} of ${page.pages.toLocaleString('en-US')}</span>
      ${page.pages > 10 ? `<form id="catalog-jump-form" class="catalog-jump"><label for="catalog-jump">Go to page</label><input id="catalog-jump" type="number" min="1" max="${page.pages}" value="${page.page+1}"><button type="submit">Go</button></form>` : ''}`;
  } catch (error) {
    if (request !== state.catalogRequest) return;
    $('#catalog-results').innerHTML = empty('plug','Directory unavailable',esc(error.message));
  }
}
function bookingRow(booking) {
  const driver = state.actor.kind === 'DRIVER';
  const owner = booking.ownerId === state.actor.id;
  return `<article class="booking-row"><span class="booking-status-icon ${booking.status.toLowerCase()}">${svg(booking.status === 'CANCELLED' ? 'check' : 'bolt',19)}</span>
    <div class="booking-primary"><strong>${esc(booking.stationName)}</strong><small>${esc(booking.stationAddress)}, ${esc(booking.stationCity)}</small>
      ${driver && booking.accessNote ? `<span class="access-instructions">Access: ${esc(booking.accessNote)}</span>` : ''}</div>
    <div><span class="booking-column-label">Time</span><strong>${fullDate(booking.startAt)}</strong><small>to ${new Intl.DateTimeFormat('en-US',{hour:'numeric',minute:'2-digit'}).format(new Date(booking.endAt))}</small></div>
    <div><span class="booking-column-label">${driver ? 'Charge estimate' : owner ? (state.actor.kind === 'PLATFORM' ? 'EC revenue' : 'Your share') : 'Total'}</span><strong>${money(owner && state.actor.kind !== 'PLATFORM' ? booking.totalCents - booking.platformFeeCents : booking.totalCents, booking.countryCode)}</strong><small>Payment simulated</small></div>
    <div class="booking-row-actions"><span class="booking-badge ${booking.status.toLowerCase()}">${booking.status === 'CANCELLED' ? 'Cancelled' : 'Confirmed'}</span>
      ${driver && booking.status === 'CONFIRMED' ? `<a class="text-action" href="${esc(directionsUrl(booking.stationAddress,booking.stationCity,booking.countryCode,booking.stationLatitude,booking.stationLongitude))}" target="_blank" rel="noopener" aria-label="Directions to ${esc(booking.stationName)} in Google Maps">${svg('pin',14)} Directions</a>` : ''}
      <button type="button" class="text-action" data-payment="${booking.id}">Payment detail</button>
      ${booking.status === 'CONFIRMED' && new Date(booking.startAt) > new Date() ? `<button type="button" class="text-action danger" data-cancel="${booking.id}">Cancel</button>` : ''}</div>
  </article>`;
}
function renderNextTrip() {
  const next = state.bookings.filter(booking => booking.status === 'CONFIRMED' && new Date(booking.startAt) > new Date())
    .sort((a,b) => new Date(a.startAt) - new Date(b.startAt))[0];
  if (!next) return `<div class="next-trip next-trip-empty"><span class="next-trip-icon">${svg('calendar',22)}</span><div><strong>No upcoming charge</strong><p>Find a charger and your next reservation will appear here.</p></div><button type="button" class="button button-outline" data-view="discover">Explore chargers ${svg('arrow',16)}</button></div>`;
  const date = new Date(next.startAt);
  return `<div class="next-trip"><div class="next-trip-date"><span>${new Intl.DateTimeFormat('en-US',{month:'short'}).format(date)}</span><strong>${new Intl.DateTimeFormat('en-US',{day:'numeric'}).format(date)}</strong><small>${new Intl.DateTimeFormat('en-US',{weekday:'short'}).format(date)}</small></div>
    <div class="next-trip-main"><span class="next-trip-label">Your next charge</span><h2>${esc(next.stationName)}</h2><p>${svg('pin',15)} ${esc(next.stationAddress)}, ${esc(next.stationCity)}</p>
      <span class="next-trip-time">${svg('clock',15)} ${new Intl.DateTimeFormat('en-US',{hour:'numeric',minute:'2-digit'}).format(date)} to ${new Intl.DateTimeFormat('en-US',{hour:'numeric',minute:'2-digit'}).format(new Date(next.endAt))}</span></div>
    <a class="button button-outline" href="${esc(directionsUrl(next.stationAddress,next.stationCity,next.countryCode,next.stationLatitude,next.stationLongitude))}" target="_blank" rel="noopener" aria-label="Directions to ${esc(next.stationName)} in Google Maps">${svg('pin',17)} Directions</a></div>`;
}
function renderReservations(driver) {
  const title = driver ? 'Your trips, all in one place.' : state.actor.kind === 'ADMIN' ? 'Every reservation.' : 'Incoming reservations.';
  const copy = driver ? 'Your confirmed slots and access instructions are here whenever you need them.'
    : 'See who is coming, when a charger is reserved, and the estimated payout.';
  const pager = state.bookingPager, data = pager.result;
  return `<section class="view reservations-view">
    ${pageHeading(driver ? 'My trips' : 'Reservations', title, copy, driver ? `<button class="button button-primary" data-view="discover">${svg('compass',17)} Find a charger</button>` : '')}
    ${driver ? renderNextTrip() : ''}
    <div class="reservation-summary"><div><span>Confirmed</span><strong>${data ? data.confirmed : '—'}</strong></div><div><span>Cancelled</span><strong>${data ? data.cancelled : '—'}</strong></div><p>${driver ? 'You can cancel a confirmed reservation before it starts.' : 'Reservations update as drivers book or cancel charging time.'}</p></div>
    <div class="reservation-controls"><div class="reservation-tabs">${[['','All'],['CONFIRMED','Confirmed'],['CANCELLED','Cancelled']].map(([value,label]) => `<button type="button" data-booking-status="${value}" class="${pager.status === value ? 'active' : ''}">${label}</button>`).join('')}</div>
      <label><span>Country</span><select id="booking-country"><option value="">All countries</option><option value="CZ" ${pager.country === 'CZ' ? 'selected' : ''}>Czechia</option><option value="US" ${pager.country === 'US' ? 'selected' : ''}>United States</option></select></label></div>
    <div class="booking-list">${!data ? '<div class="catalog-loading">Loading reservations…</div>' : data.items.length ? data.items.map(bookingRow).join('') : empty('calendar', driver ? 'No trips match these filters' : 'No reservations match these filters', 'Try another status or country.')}</div>
    ${data && data.pages > 1 ? `<nav class="catalog-pagination" aria-label="Reservation pages"><button type="button" data-booking-page="${data.page - 1}" ${data.page === 0 ? 'disabled' : ''}>Previous</button><span>Page ${data.page + 1} of ${data.pages}</span><button type="button" data-booking-page="${data.page + 1}" ${data.page >= data.pages - 1 ? 'disabled' : ''}>Next</button></nav>` : ''}
  </section>`;
}
async function loadBookingPage() {
  if (state.view !== 'trips' && state.view !== 'bookings') return;
  const request = ++state.bookingRequest;
  const pager = state.bookingPager;
  pager.result = null;
  $('#main-content').innerHTML = renderReservations(state.actor.kind === 'DRIVER');
  const params = new URLSearchParams({status:pager.status,country:pager.country,page:String(pager.page),size:String(pager.size)});
  try {
    const result = await api('/bookings/page?' + params);
    if (request !== state.bookingRequest || !['trips','bookings'].includes(state.view)) return;
    pager.result = result;
    $('#main-content').innerHTML = renderReservations(state.actor.kind === 'DRIVER');
  } catch (error) {
    if (request !== state.bookingRequest) return;
    $('#main-content').innerHTML = `<section class="view">${empty('calendar','Reservations unavailable',esc(error.message))}</section>`;
  }
}
function renderInbox() {
  const unread = state.notices.filter(item => !item.read).length;
  return `<section class="view inbox-view">
    ${pageHeading('Inbox', 'Stay in the loop.', 'Updates about your reservations, listings, and network activity.')}
    <div class="inbox-header"><strong>${unread} unread</strong><span>${state.notices.length} recent notifications</span></div>
    <div class="inbox-list">${state.notices.length ? state.notices.map(item => `<article class="inbox-item ${item.read ? '' : 'unread'}"><span class="inbox-type-icon">${svg(item.type === 'BOOKING' ? 'calendar' : 'check',21)}</span>
      <div><div class="inbox-title"><h3>${esc(item.title)}</h3><time>${fullDate(item.createdAt)}</time></div><p>${esc(item.body)}</p></div>
      ${item.read ? '<span class="read-label">Read</span>' : `<button type="button" class="button button-outline" data-read="${item.id}">Mark read</button>`}</article>`).join('') : empty('bell','All quiet for now','Your booking and listing updates will appear here.')}</div>
  </section>`;
}

function localInput(value) {
  const pad = number => String(number).padStart(2,'0');
  return `${value.getFullYear()}-${pad(value.getMonth()+1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
}
function suggestSlot() {
  const start = state.timeFilter && new Date(state.timeFilter.startAt) > new Date()
    ? new Date(state.timeFilter.startAt) : new Date(Date.now() + 2 * 60 * 60 * 1000);
  if (!state.timeFilter) start.setMinutes(0,0,0);
  $('#start-at').value = localInput(start);
  $('#end-at').value = localInput(new Date(start.getTime() + (state.timeFilter?.durationMinutes || 60) * 60 * 1000));
  window.refreshCustomControls?.();
}
async function openBooking(id) {
  if (state.actor.kind !== 'DRIVER') { toast('Switch to a driver profile to reserve a charger.', 'error'); return; }
  try {
    const station = state.stations.find(item => item.id === id) || state.saved.find(item => item.id === id) || await api('/stations/' + id);
    state.selectedStation = station;
    $('#booking-station-name').textContent = station.name;
    $('#booking-station-detail').textContent = station.address + ', ' + station.city;
    $('#booking-highlights').innerHTML = `<span>${svg('bolt',16)} ${station.powerKw} kW</span><span>${esc(station.connector)}</span><span>${money(station.pricePerHourCents,station.countryCode)} / hour</span>`;
    $('#book-button').textContent = state.previewReadOnly ? 'Reservation disabled in preview' : 'Confirm reservation';
    $('#booking-fineprint').textContent = state.previewReadOnly
      ? 'You can check availability in this demo. Reservations and payments cannot be created here.'
      : 'Payment is simulated. No card or money is involved.';
    suggestSlot(); $('#booking-dialog').showModal(); await checkAvailability();
  } catch (error) { toast(error.message, 'error'); }
}
async function checkAvailability() {
  if (!state.selectedStation || !$('#booking-dialog').open) return;
  const request = ++state.availabilityRequest;
  const start = new Date($('#start-at').value), end = new Date($('#end-at').value);
  const box = $('#availability'), button = $('#book-button');
  if (Number.isNaN(+start) || Number.isNaN(+end)) { box.textContent = 'Choose a start and end time.'; button.disabled = true; return; }
  const minutes = (end - start) / 60000;
  if (minutes < 30 || minutes > 240 || start <= new Date()) {
    box.textContent = 'Choose a future slot between 30 minutes and 4 hours.';
    box.classList.add('error'); button.disabled = true; return;
  }
  box.textContent = 'Checking this slot...'; box.classList.remove('error'); button.disabled = true;
  try {
    const availability = await api(`/stations/${state.selectedStation.id}/availability?startAt=${encodeURIComponent(start.toISOString())}&endAt=${encodeURIComponent(end.toISOString())}`);
    if (request !== state.availabilityRequest || !$('#booking-dialog').open) return;
    box.innerHTML = availability.available ? `<strong>Available</strong><span>${money(availability.quoteCents,state.selectedStation.countryCode)} for this slot · simulated payment</span>`
      : `<strong>Unavailable</strong><span>${esc(availability.reason)}</span>`;
    box.classList.toggle('error', !availability.available);
    button.disabled = state.previewReadOnly || !availability.available;
  } catch (error) {
    if (request !== state.availabilityRequest || !$('#booking-dialog').open) return;
    box.textContent = error.message; box.classList.add('error');
  }
}
async function submitBooking(event) {
  event.preventDefault();
  try {
    await api('/bookings', {method:'POST', body:JSON.stringify({
      stationId: state.selectedStation.id,
      startAt: new Date($('#start-at').value).toISOString(),
      endAt: new Date($('#end-at').value).toISOString()
    })});
    $('#booking-dialog').close(); state.selectedStation = null;
    toast('Reservation confirmed. Your charger is held for you.');
    state.view = 'trips'; await loadActorData(); render(); window.scrollTo({top:0,behavior:'instant'});
    setTimeout(async () => { if (state.actor?.kind === 'DRIVER') { await loadActorData(); renderChrome(); } }, 2200);
  } catch (error) { toast(error.message,'error'); await checkAvailability(); }
}
function closeDialog(id) {
  const dialog = $('#' + id);
  if (dialog?.open) dialog.close();
  if (id === 'station-dialog' && state.picker) { state.picker.remove(); state.picker = null; state.pickerPin = null; }
}
function openStationDialog() {
  if (!['PERSON','COMPANY','PLATFORM'].includes(state.actor.kind)) {
    toast('Create a host or company profile first.', 'error'); return;
  }
  $('#station-form').reset();
  const country = state.owned[0]?.countryCode || state.country;
  $('#station-country').value = country;
  window.refreshCustomControls?.();
  updateStationCityOptions(country);
  $('#price-currency').textContent = country === 'US' ? 'USD' : 'CZK';
  $('#station-submit').textContent = state.actor.kind === 'PLATFORM' ? 'Publish EC station' : 'Submit station for review';
  $('#station-dialog').showModal();
  setTimeout(() => mountPicker(country), 80);
}
function updateStationCityOptions(country) {
  $('#station-city-options').innerHTML = places[country].slice(1)
    .map(place => `<option value="${esc(place[4] || place[0])}"></option>`).join('');
}
function setPickerPin(latlng, label = 'Location pin placed') {
  $('#station-latitude').value = latlng.lat.toFixed(6);
  $('#station-longitude').value = latlng.lng.toFixed(6);
  $('#pin-summary-title').textContent = label;
  $('#pin-summary-coordinates').textContent = latlng.lat.toFixed(4) + ', ' + latlng.lng.toFixed(4) + ' · click the map to adjust';
  if (state.pickerPin) state.pickerPin.setLatLng(latlng);
  else state.pickerPin = L.circleMarker(latlng,{radius:10,color:'#fff',weight:3,fillColor:'#4068fa',fillOpacity:1}).addTo(state.picker);
}
function mountPicker(country) {
  if (state.picker) { state.picker.remove(); state.pickerPin = null; }
  const center = places[country][1];
  state.picker = L.map('picker-map', {zoomControl:true, minZoom:3, maxZoom:18}).setView([center[1],center[2]],12);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18, attribution:'&copy; OpenStreetMap contributors'}).addTo(state.picker);
  setPickerPin(state.picker.getCenter(), 'Pinned near ' + center[0]);
  state.picker.on('click', event => setPickerPin(event.latlng));
  state.picker.invalidateSize();
}
async function submitStation(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const body = {
    name:form.get('name'), city:form.get('city'), address:form.get('address'),
    countryCode:form.get('countryCode'), connector:form.get('connector'),
    powerKw:Number(form.get('powerKw')), pricePerHourCents:Math.round(Number(form.get('price')) * 100),
    accessNote:form.get('accessNote'), latitude:Number(form.get('latitude')), longitude:Number(form.get('longitude'))
  };
  try {
    const station = await api('/stations', {method:'POST',body:JSON.stringify(body)});
    closeDialog('station-dialog');
    toast(station.listingStatus === 'APPROVED' ? 'Station published and available to drivers.' : 'Station submitted for review.');
    state.view = state.actor.kind === 'COMPANY' ? 'fleet' : 'stations';
    await loadActorData(); render();
    setTimeout(async () => { await loadActorData(); renderChrome(); }, 2200);
  } catch (error) { toast(error.message,'error'); }
}
async function submitAccount(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    const user = await api('/users',{method:'POST',body:JSON.stringify({name:form.get('name'),kind:form.get('kind')})});
    state.users.push(user); closeDialog('account-dialog'); await setActor(user.id);
    toast('Demo profile created.');
  } catch (error) { toast(error.message,'error'); }
}
async function showTelemetry(id) {
  try {
    const station = state.owned.find(item => item.id === id) || state.pending.find(item => item.id === id)
      || state.adminCatalog.result?.items.find(item => item.id === id);
    const data = await api('/stations/' + id + '/telemetry-preview');
    $('#telemetry-name').textContent = station?.name || 'Station pulse';
    $('#telemetry-content').innerHTML = `<div class="telemetry-status"><span class="connection-dot"></span><strong>${data.state === 'CHARGING' ? 'Charging' : data.state === 'AVAILABLE' ? 'Available' : 'Offline'}</strong><small>Generated preview, not live hardware data</small></div>
      <div class="telemetry-metrics">${metric('Energy today',data.energyKwhToday+' kWh')}${metric('Utilization',data.utilizationPercent+'%')}${metric('Rated power',data.powerKw+' kW')}</div>
      <div class="telemetry-bar"><span style="width:${data.utilizationPercent}%"></span></div><p class="modal-fineprint">OCPP hardware telemetry is simulated. Values are plausible examples for this station and date.</p>`;
    $('#telemetry-dialog').showModal();
  } catch (error) { toast(error.message,'error'); }
}
function renderScheduleBlocks(blocks) {
  $('#schedule-count').textContent = blocks.length ? `${blocks.length} upcoming` : 'Open schedule';
  $('#schedule-blocks').innerHTML = blocks.length ? blocks.map(block => `<article class="schedule-block">
    <span class="schedule-block-icon">${svg('calendar',18)}</span><div><strong>${fullDate(block.startAt)}</strong><small>Until ${fullDate(block.endAt)}${block.reason ? ' · ' + esc(block.reason) : ''}</small></div>
    <button type="button" class="text-action" data-remove-block="${block.id}" aria-label="Remove blocked time">Remove</button></article>`).join('')
    : `<div class="schedule-empty">${svg('check',19)} Every upcoming hour is open unless a driver has booked it.</div>`;
}
const weekNames = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
function minuteOptions(value, closing = false) {
  const pad = number => String(number).padStart(2,'0');
  let html = '';
  for (let minute = closing ? 30 : 0; minute <= (closing ? 1440 : 1410); minute += 30) {
    const label = minute === 1440 ? '24:00' : `${pad(Math.floor(minute / 60))}:${pad(minute % 60)}`;
    html += `<option value="${minute}" ${minute === value ? 'selected' : ''}>${label}</option>`;
  }
  return html;
}
function renderWeeklySchedule(schedule) {
  const zones = schedule.zoneId === 'Europe/Prague' ? [['Europe/Prague','Prague · CET/CEST']]
    : [['America/New_York','Eastern'],['America/Chicago','Central'],['America/Denver','Mountain'],
       ['America/Phoenix','Arizona'],['America/Los_Angeles','Pacific'],['America/Anchorage','Alaska'],['Pacific/Honolulu','Hawaii']];
  $('#weekly-zone').innerHTML = zones.map(([value,label]) => `<option value="${value}" ${value === schedule.zoneId ? 'selected' : ''}>${label}</option>`).join('');
  $('#weekly-status').textContent = schedule.configured ? 'Your regular hours' : 'Open around the clock';
  $('#reset-weekly').hidden = !schedule.configured;
  $('#weekly-days').innerHTML = schedule.days.map(day => `<div class="weekly-day ${day.enabled ? '' : 'closed'}" data-weekday="${day.dayOfWeek}">
    <label class="weekly-switch"><input type="checkbox" ${day.enabled ? 'checked' : ''}><span class="weekly-switch-track"></span><strong>${weekNames[day.dayOfWeek - 1]}</strong></label>
    <div class="weekly-time-range"><select aria-label="${weekNames[day.dayOfWeek - 1]} opens">${minuteOptions(day.opensMinute)}</select><span>to</span><select aria-label="${weekNames[day.dayOfWeek - 1]} closes">${minuteOptions(day.closesMinute, true)}</select></div>
    <span class="weekly-closed-label">Closed</span></div>`).join('');
  window.refreshCustomControls?.();
}
function setScheduleTab(tab) {
  $('#weekly-panel').hidden = tab !== 'weekly';
  $('#blocks-panel').hidden = tab !== 'blocks';
  document.querySelectorAll('[data-schedule-tab]').forEach(button => {
    const active = button.dataset.scheduleTab === tab;
    button.classList.toggle('active',active);
    button.setAttribute('aria-selected',String(active));
  });
}
async function submitWeekly(event) {
  event.preventDefault();
  if (!state.scheduleStation) return;
  const days = [...document.querySelectorAll('.weekly-day')].map(row => ({
    dayOfWeek:Number(row.dataset.weekday), enabled:row.querySelector('input').checked,
    opensMinute:Number(row.querySelectorAll('select')[0].value), closesMinute:Number(row.querySelectorAll('select')[1].value)
  }));
  if (days.some(day => day.opensMinute >= day.closesMinute)) { toast('Closing time must be after opening time.','error'); return; }
  try {
    const result = await api('/stations/' + state.scheduleStation.id + '/weekly-hours', {method:'PUT',body:JSON.stringify({zoneId:$('#weekly-zone').value,days})});
    renderWeeklySchedule(result); toast('Weekly hours saved. New reservations will follow this schedule.');
  } catch (error) { toast(error.message,'error'); }
}
async function resetWeekly() {
  if (!state.scheduleStation) return;
  try {
    await api('/stations/' + state.scheduleStation.id + '/weekly-hours',{method:'DELETE'});
    renderWeeklySchedule(await api('/stations/' + state.scheduleStation.id + '/weekly-hours'));
    toast('Station is open around the clock again.');
  } catch (error) { toast(error.message,'error'); }
}
function applyWeeklyPreset(preset) {
  document.querySelectorAll('.weekly-day').forEach((row,index) => {
    const enabled = preset === 'everyday' || index < 5;
    row.querySelector('input').checked = enabled;
    row.classList.toggle('closed',!enabled);
    const selects = row.querySelectorAll('select');
    selects[0].value = String(preset === 'everyday' ? 0 : 480);
    selects[1].value = String(preset === 'everyday' ? 1440 : 1200);
  });
  window.refreshCustomControls?.();
}
async function refreshSchedule() {
  if (!state.scheduleStation) return;
  renderScheduleBlocks(await api('/stations/' + state.scheduleStation.id + '/blocks'));
}
async function openSchedule(id) {
  try {
    const station = state.owned.find(item => item.id === id) || state.pending.find(item => item.id === id)
      || state.adminCatalog.result?.items.find(item => item.id === id) || await api('/stations/' + id);
    state.scheduleStation = station;
    $('#schedule-station-name').textContent = station.name;
    const start = new Date(); start.setDate(start.getDate() + 1); start.setHours(10,0,0,0);
    $('#block-start-at').value = localInput(start);
    $('#block-end-at').value = localInput(new Date(start.getTime() + 2 * 60 * 60 * 1000));
    $('#block-reason').value = '';
    window.refreshCustomControls?.();
    const [blocks, weekly] = await Promise.all([
      api('/stations/' + id + '/blocks'), api('/stations/' + id + '/weekly-hours')
    ]);
    renderScheduleBlocks(blocks);
    renderWeeklySchedule(weekly);
    $('#schedule-dialog .modal-subtitle').textContent = state.previewReadOnly
      ? 'Inspect regular opening hours and blocked dates. Changes are disabled in this public demo.'
      : 'Set regular opening hours and close individual dates when needed. Confirmed reservations stay in place.';
    $('#schedule-dialog').querySelectorAll('#weekly-form input, #weekly-form select').forEach(control => {
      control.disabled = state.previewReadOnly;
    });
    window.refreshCustomControls?.();
    setScheduleTab('weekly');
    closeDialog('telemetry-dialog');
    $('#schedule-dialog').showModal();
  } catch (error) { toast(error.message,'error'); }
}
async function submitBlock(event) {
  event.preventDefault();
  if (!state.scheduleStation) return;
  try {
    await api('/stations/' + state.scheduleStation.id + '/blocks', {method:'POST',body:JSON.stringify({
      startAt:new Date($('#block-start-at').value).toISOString(),
      endAt:new Date($('#block-end-at').value).toISOString(),
      reason:$('#block-reason').value
    })});
    toast('Blocked time saved. Drivers cannot reserve this slot.');
    await refreshSchedule();
  } catch (error) { toast(error.message,'error'); }
}
async function toggleSaved(id) {
  const wasSaved = savedId(id);
  try {
    await api('/saved-stations/' + id, {method:wasSaved ? 'DELETE' : 'PUT'});
    state.saved = await api('/saved-stations');
    renderChrome();
    if (state.view === 'saved') $('#main-content').innerHTML = renderSaved();
    if (state.view === 'discover') renderResults();
    const popupSave = document.querySelector('.map-popup [data-save="' + id + '"]');
    if (popupSave) popupSave.textContent = wasSaved ? 'Save for later' : 'Remove from saved';
    toast(wasSaved ? 'Removed from saved chargers.' : 'Charger saved to your places.');
  } catch (error) { toast(error.message,'error'); }
}
async function performAction(target) {
  const bookingStatus = target.closest('[data-booking-status]'); if (bookingStatus) {
    state.bookingPager.status = bookingStatus.dataset.bookingStatus;
    state.bookingPager.page = 0; await loadBookingPage(); return;
  }
  const bookingPage = target.closest('[data-booking-page]'); if (bookingPage) {
    state.bookingPager.page = Number(bookingPage.dataset.bookingPage);
    await loadBookingPage(); window.scrollTo({top:0,behavior:'smooth'}); return;
  }
  const catalogPage = target.closest('[data-catalog-page]'); if (catalogPage) {
    state.adminCatalog.page = Number(catalogPage.dataset.catalogPage);
    await loadAdminCatalog(); window.scrollTo({top:0,behavior:'smooth'}); return;
  }
  const save = target.closest('[data-save]'); if (save) return toggleSaved(save.dataset.save);
  if (target.closest('[data-time-search]')) return openTimeSearch();
  if (target.closest('[data-clear-time]')) {
    state.timeFilter = null; state.availableCount = 0; syncTimeFilter(); queryMap(); return;
  }
  const book = target.closest('[data-book]'); if (book) return openBooking(book.dataset.book);
  const focus = target.closest('[data-focus]'); if (focus) {
    const station = state.stations.find(item => item.id === focus.dataset.focus);
    if (station) focusStation(station);
    return;
  }
  const view = target.closest('[data-view]'); if (view) return selectView(view.dataset.view);
  if (target.closest('[data-add-station]')) return openStationDialog();
  const close = target.closest('[data-close]'); if (close) return closeDialog(close.dataset.close);
  const schedule = target.closest('[data-schedule]'); if (schedule) return openSchedule(schedule.dataset.schedule);
  const scheduleTab = target.closest('[data-schedule-tab]'); if (scheduleTab) return setScheduleTab(scheduleTab.dataset.scheduleTab);
  const weeklyPreset = target.closest('[data-weekly-preset]'); if (weeklyPreset) return applyWeeklyPreset(weeklyPreset.dataset.weeklyPreset);
  if (target.closest('[data-reset-weekly]')) return resetWeekly();
  const removeBlock = target.closest('[data-remove-block]'); if (removeBlock) {
    try {
      await api('/stations/' + state.scheduleStation.id + '/blocks/' + removeBlock.dataset.removeBlock,{method:'DELETE'});
      toast('Blocked time removed.'); await refreshSchedule();
    } catch (error) { toast(error.message,'error'); }
    return;
  }
  const telemetry = target.closest('[data-telemetry]'); if (telemetry) return showTelemetry(telemetry.dataset.telemetry);
  const toggle = target.closest('[data-toggle]'); if (toggle) {
    try { await api('/stations/'+toggle.dataset.toggle+'/status',{method:'PATCH',body:JSON.stringify({active:toggle.dataset.active !== 'true'})});
      toast('Station availability updated.'); await loadActorData(); render();
    } catch (error) { toast(error.message,'error'); } return;
  }
  const fleet = target.closest('[data-fleet]'); if (fleet) {
    try { const result = await api('/my-stations/status',{method:'PATCH',body:JSON.stringify({active:fleet.dataset.fleet === 'true'})});
      toast(result.updated + ' stations updated.'); await loadActorData(); render();
    } catch (error) { toast(error.message,'error'); } return;
  }
  const decision = target.closest('[data-decision]'); if (decision) {
    try { await api('/admin/stations/'+decision.dataset.decision+'/decision',{method:'POST',body:JSON.stringify({approve:decision.dataset.approve === 'true'})});
      toast(decision.dataset.approve === 'true' ? 'Station approved.' : 'Listing declined.');
      await loadActorData(); render();
    } catch (error) { toast(error.message,'error'); } return;
  }
  const cancel = target.closest('[data-cancel]'); if (cancel) {
    try { await api('/bookings/'+cancel.dataset.cancel+'/cancel',{method:'POST'}); toast('Reservation cancelled.');
      await loadActorData(); render();
    } catch (error) { toast(error.message,'error'); } return;
  }
  const payment = target.closest('[data-payment]'); if (payment) {
    try { const charge = await api('/bookings/'+payment.dataset.payment+'/payment-preview');
      toast(charge.status === 'PENDING' ? 'Payment preview is processing.' : `Payment ${charge.status.toLowerCase()} · ${money(charge.totalCents,state.bookings.find(b=>b.id===payment.dataset.payment)?.countryCode)} total · no money charged.`);
    } catch (error) { toast(error.message,'error'); } return;
  }
  const read = target.closest('[data-read]'); if (read) {
    try { await api('/notifications/'+read.dataset.read+'/read',{method:'PATCH'}); await loadActorData(); render();
    } catch (error) { toast(error.message,'error'); }
  }
}
async function init() {
  try {
    state.users = await api('/users');
    state.system = await api('/system');
    state.previewReadOnly = state.system.readOnly === true;
    const saved = localStorage.getItem('ec-demo-actor');
    const initial = state.users.find(item => item.id === saved) || state.users.find(item => item.kind === 'DRIVER');
    await setActor(initial.id);
    setInterval(async () => {
      if (!state.actor) return;
      try {
        state.notices = await api('/notifications');
        renderChrome();
        if (state.view === 'inbox') $('#main-content').innerHTML = renderInbox();
      } catch { /* Keep the last known inbox when local services restart. */ }
    }, 12000);
  } catch (error) { toast('Could not load the local preview: ' + error.message,'error'); }
}
document.addEventListener('click', event => performAction(event.target));
document.addEventListener('submit', event => {
  if (event.target.id === 'catalog-jump-form') {
    event.preventDefault();
    const last = state.adminCatalog.result?.pages || 1;
    state.adminCatalog.page = Math.max(0, Math.min(last - 1, Number($('#catalog-jump').value || 1) - 1));
    loadAdminCatalog();
  }
  if (event.target.id === 'booking-form') submitBooking(event);
  if (event.target.id === 'time-search-form') submitTimeSearch(event);
  if (event.target.id === 'weekly-form') submitWeekly(event);
  if (event.target.id === 'block-form') submitBlock(event);
  if (event.target.id === 'station-form') submitStation(event);
  if (event.target.id === 'account-form') submitAccount(event);
});
document.addEventListener('change', event => {
  if (event.target.closest('.weekly-switch')) {
    event.target.closest('.weekly-day').classList.toggle('closed',!event.target.checked);
  }
  if (event.target.id === 'actor') setActor(event.target.value);
  if (event.target.id === 'booking-country') {
    state.bookingPager.country = event.target.value;
    state.bookingPager.page = 0; loadBookingPage();
  }
  if (event.target.id === 'country-filter') {
    state.country = event.target.value; state.place = 1; state.city = ''; state.connector = ''; render();
  }
  if (event.target.id === 'place-filter') {
    state.place = Number(event.target.value); state.city = '';
    const place = places[state.country][state.place];
    $('#city-filter').value = '';
    $('#map-location-label').textContent = place[0];
    moveMapTo(place);
  }
  if (event.target.id === 'connector-filter') { state.connector = event.target.value; clearFocus(); queryMap(); }
  if (event.target.id === 'station-country') {
    $('#price-currency').textContent = event.target.value === 'US' ? 'USD' : 'CZK';
    updateStationCityOptions(event.target.value);
    $('#station-city').value = '';
    if (state.picker) mountPicker(event.target.value);
  }
  const catalogFilter = { 'catalog-country':'country', 'catalog-status':'status', 'catalog-owner':'ownerKind' }[event.target.id];
  if (catalogFilter) {
    state.adminCatalog[catalogFilter] = event.target.value;
    state.adminCatalog.page = 0;
    loadAdminCatalog();
  }
  if (event.target.id === 'start-at' && $('#start-at').value && $('#end-at').value
      && new Date($('#end-at').value) <= new Date($('#start-at').value)) {
    $('#end-at').value = localInput(new Date(new Date($('#start-at').value).getTime() + 60 * 60 * 1000));
    window.refreshCustomControls?.();
  }
  if (event.target.id === 'start-at' || event.target.id === 'end-at') checkAvailability();
  if (event.target.id === 'block-start-at' && $('#block-start-at').value && $('#block-end-at').value
      && new Date($('#block-end-at').value) <= new Date($('#block-start-at').value)) {
    $('#block-end-at').value = localInput(new Date(new Date($('#block-start-at').value).getTime() + 2 * 60 * 60 * 1000));
    window.refreshCustomControls?.();
  }
});
document.addEventListener('input', event => {
  if (event.target.id === 'catalog-query') {
    state.adminCatalog.query = event.target.value;
    state.adminCatalog.page = 0;
    clearTimeout(catalogTimer); catalogTimer = setTimeout(loadAdminCatalog, 300);
  }
  if (event.target.id === 'city-filter') {
    state.city = event.target.value;
    clearFocus();
    clearTimeout(filterTimer); filterTimer = setTimeout(() => {
      const match = exactPlace(state.country, event.target.value);
      if (match) {
        state.place = match.index;
        state.city = match.place[4] || match.place[0];
        $('#place-filter').value = String(match.index);
        window.refreshCustomControls?.();
        $('#map-location-label').textContent = match.place[0];
        moveMapTo(match.place);
      }
      queryMap();
    }, 350);
  }
  if (event.target.id === 'station-city') {
    clearTimeout(pickerTimer); pickerTimer = setTimeout(() => {
      const match = exactPlace($('#station-country').value, event.target.value);
      if (!match || !state.picker) return;
      const latlng = L.latLng(match.place[1], match.place[2]);
      state.picker.setView(latlng, match.place[3]);
      setPickerPin(latlng, 'Pinned near ' + match.place[0]);
    }, 350);
  }
});
document.addEventListener('keydown', event => {
  if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-focus]')) {
    event.preventDefault(); performAction(event.target);
  }
});
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => { if (event.target === dialog) closeDialog(dialog.id); });
  dialog.addEventListener('close', () => {
    if (dialog.id === 'station-dialog' && state.picker) { state.picker.remove(); state.picker = null; state.pickerPin = null; }
  });
});
$('#notification-button').addEventListener('click', () => selectView('inbox'));
$('#menu-button').addEventListener('click', () => {
  state.sidebarOpen = !state.sidebarOpen;
  document.body.classList.toggle('sidebar-open', state.sidebarOpen);
  $('#menu-button').setAttribute('aria-expanded',String(state.sidebarOpen));
});
init();

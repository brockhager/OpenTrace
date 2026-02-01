// Search functionality
const form = document.getElementById('searchForm');
const queryInput = document.getElementById('query');
const resultsEl = document.getElementById('results');
const statusEl = document.getElementById('status');

// Location search elements
const locationInput = document.getElementById('location');
const radiusInput = document.getElementById('radius');
const useLocationBtn = document.getElementById('useLocation');
const clearLocationBtn = document.getElementById('clearLocation');

let userLocation = null;

if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = queryInput.value.trim();
    const location = locationInput?.value.trim();
    
    if (!q && !location && !userLocation) {
      statusEl.textContent = 'Please enter a search term or location.';
      return;
    }
    
    statusEl.textContent = 'Searching...';
    resultsEl.innerHTML = '';

    try {
      // Build search URL with location parameters
      let searchUrl = `/search?q=${encodeURIComponent(q || '')}`;
      
      if (userLocation) {
        searchUrl += `&lat=${userLocation.lat}&lng=${userLocation.lng}`;
        if (radiusInput?.value) {
          searchUrl += `&radius_km=${radiusInput.value}`;
        }
      } else if (location) {
        searchUrl += `&location=${encodeURIComponent(location)}`;
      }
      
      const res = await fetch(searchUrl);
      if (!res.ok) throw new Error('Search failed');
      const payload = await res.json();
      const items = Array.isArray(payload) ? payload : (payload.results || []);
      
      if (items.length === 0) {
        statusEl.textContent = 'No results found. Try different search terms or location.';
        resultsEl.innerHTML = '';
        return;
      }
      
      statusEl.textContent = '';
      resultsEl.innerHTML = items.map(p => renderCard(p)).join('');
    } catch (err) {
      statusEl.textContent = 'Search failed — try again.';
    }
  });
}

// Location functionality
if (useLocationBtn) {
  useLocationBtn.addEventListener('click', async () => {
    if (!navigator.geolocation) {
      statusEl.textContent = 'Geolocation is not supported by your browser.';
      return;
    }
    
    useLocationBtn.disabled = true;
    useLocationBtn.textContent = 'Getting location...';
    
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        userLocation = {
          lat: position.coords.latitude,
          lng: position.coords.longitude
        };
        
        useLocationBtn.textContent = '✓ Using my location';
        useLocationBtn.style.backgroundColor = '#34a853';
        
        // Get location name for display
        try {
          const res = await fetch(`/api/reverse-geocode?lat=${userLocation.lat}&lng=${userLocation.lng}`);
          if (res.ok) {
            const location = await res.json();
            if (locationInput) {
              locationInput.value = location.display_name;
            }
            statusEl.textContent = `Using location: ${location.display_name}`;
          }
        } catch (err) {
          statusEl.textContent = 'Using your current location';
        }
      },
      (error) => {
        useLocationBtn.disabled = false;
        useLocationBtn.textContent = 'Use my location';
        statusEl.textContent = 'Could not get your location. Please enter location manually.';
      }
    );
  });
}

if (clearLocationBtn) {
  clearLocationBtn.addEventListener('click', () => {
    userLocation = null;
    if (locationInput) locationInput.value = '';
    if (useLocationBtn) {
      useLocationBtn.disabled = false;
      useLocationBtn.textContent = 'Use my location';
      useLocationBtn.style.backgroundColor = '';
    }
    statusEl.textContent = '';
  });
}

// Admin functionality
let token = sessionStorage.getItem('opentrace_token') || null;
const loginForm = document.getElementById('loginForm');
const loginStatus = document.getElementById('loginStatus');
const reviewSection = document.getElementById('reviewSection');
const profilesEl = document.getElementById('profiles');

function getAuthHeaders() {
  if (!token) return {};
  return { 'Authorization': 'Bearer ' + token };
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const message = await res.text();
    throw new Error(message || 'Request failed');
  }
  if (res.status === 204) return null;
  return res.json();
}

if (loginForm) {
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    loginStatus.textContent = 'Signing in...';

    try {
      const res = await fetch('/admin/login', {
        method: 'POST', 
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, password})
      });
      if (!res.ok) throw new Error('Login failed');
      const data = await res.json();
      token = data.access_token;
      sessionStorage.setItem('opentrace_token', token);
      loginStatus.textContent = 'Signed in';
      document.getElementById('loginSection').style.display = 'none';
      reviewSection.style.display = 'block';
      await loadUnconfirmed();
    } catch (err) {
      loginStatus.textContent = 'Sign-in failed — check credentials';
    }
  });
}

const loginSection = document.getElementById('loginSection');
if (reviewSection && token && loginSection) {
  loginSection.style.display = 'none';
  reviewSection.style.display = 'block';
  loadUnconfirmed();
}

async function loadUnconfirmed(){
  if (!profilesEl) return;
  profilesEl.innerHTML = 'Loading...';
  try {
    // Try new Person endpoint first, fallback to old profile endpoint
    let res = await fetch('/admin/review-persons', { 
      headers: { 'Authorization': 'Bearer ' + token }
    });
    
    if (!res.ok) {
      // Fallback to old endpoint for backward compatibility
      res = await fetch('/admin/review-profiles', { 
        headers: { 'Authorization': 'Bearer ' + token }
      });
    }
    
    if (!res.ok) throw new Error('Failed to load');
    const data = await res.json();
    const profiles = data.profiles || [];
    if (profiles.length === 0) {
      profilesEl.innerHTML = '<em>No unconfirmed profiles</em>';
      return;
    }
    profilesEl.innerHTML = profiles.map(p => renderRow(p)).join('');
  } catch (err) {
    profilesEl.innerHTML = '<em>Failed to load profiles</em>';
  }
}

function renderRow(p){
  // Handle both new Person and old PersonProfile formats
  const location = p.last_seen_location || p.source_url || 'Unknown location';
  const author = p.author_name || p.primary_source || 'Unknown source';
  const id = p.pfif_id || p.id || '';
  
  return `
    <div class="card">
      <span class="card-id">${escapeHtml(id)}</span>
      <h4>${escapeHtml(p.given_name || '')} ${escapeHtml(p.family_name || '')}</h4>
      <p>${escapeHtml(location)} — ${escapeHtml(author)}</p>
      <p><button data-pfif="${encodeURIComponent(p.pfif_id)}" class="approve">Approve</button></p>
    </div>
  `;
}

if (profilesEl) {
  profilesEl.addEventListener('click', async (e) => {
    if (!e.target.classList.contains('approve')) return;
    const pfif = decodeURIComponent(e.target.dataset.pfif);
    e.target.disabled = true;
    try {
      // Try new Person endpoint first, fallback to old profile endpoint
      let res = await fetch('/admin/approve-person', {
        method: 'POST', 
        headers: { 
          'Authorization': 'Bearer ' + token, 
          'Content-Type': 'application/json' 
        },
        body: JSON.stringify({ pfif_id: pfif, confirm: true })
      });
      
      if (!res.ok) {
        // Fallback to old endpoint for backward compatibility
        res = await fetch('/admin/approve-profile', {
          method: 'POST', 
          headers: { 
            'Authorization': 'Bearer ' + token, 
            'Content-Type': 'application/json' 
          },
          body: JSON.stringify({ pfif_id: pfif, confirm: true })
        });
      }
      
      if (!res.ok) throw new Error('Approve failed');
      await loadUnconfirmed();
    } catch (err) {
      if (loginStatus) loginStatus.textContent = 'Approve failed';
      e.target.disabled = false;
    }
  });
}

function renderCard(p) {
  const name = `${p.given_name || ''} ${p.family_name || ''}`.trim() || 'Unnamed';
  const pfif = encodeURIComponent(p.pfif_id);
  return `
    <article class="card">
      <span class="card-id">${escapeHtml(p.pfif_id || '')}</span>
      <h3>${escapeHtml(name)} <span class="meta">(${p.age_at_disappearance || '—'}, ${p.sex || '—'})</span></h3>
      <p><strong>Status:</strong> ${escapeHtml(p.status)}</p>
      <p class="meta">Source: ${escapeHtml(p.primary_source || 'Unknown')}</p>
      <p><a href="/profile.html?id=${pfif}">View details</a></p>
    </article>
  `;
}

function escapeHtml(s){
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,"&#039;");
}

// Quick search on load if ?q= is present
const params = new URLSearchParams(window.location.search);
if (params.get('q') && queryInput){
  queryInput.value = params.get('q');
  form.dispatchEvent(new Event('submit'));
}

// Persons page
const personsForm = document.getElementById('personsSearchForm');
const personsQuery = document.getElementById('personsQuery');
const personsLocation = document.getElementById('personsLocation');
const personsResults = document.getElementById('personsResults');
const personsStatus = document.getElementById('personsStatus');

if (personsForm) {
  personsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = personsQuery?.value.trim() || '';
    const location = personsLocation?.value.trim() || '';
    personsStatus.textContent = q || location ? 'Searching...' : 'Loading all confirmed profiles...';
    personsResults.innerHTML = '';
    try {
      const url = `/search?q=${encodeURIComponent(q)}&location=${encodeURIComponent(location)}`;
      const payload = await fetchJson(url);
      const items = Array.isArray(payload) ? payload : (payload.results || []);
      if (!items.length) {
        personsStatus.textContent = 'No results found.';
        return;
      }
      personsStatus.textContent = '';
      personsResults.innerHTML = items.map(renderCard).join('');
    } catch (err) {
      personsStatus.textContent = 'Search failed — try again.';
    }
  });
  personsForm.dispatchEvent(new Event('submit'));
}

// Locations page
const locationsForm = document.getElementById('locationsSearchForm');
const locationsQuery = document.getElementById('locationsQuery');
const locationsResults = document.getElementById('locationsResults');
const locationsStatus = document.getElementById('locationsStatus');

if (locationsForm) {
  locationsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = locationsQuery?.value.trim() || '';
    if (!q) {
      locationsStatus.textContent = 'Enter a location name to search.';
      locationsResults.innerHTML = '';
      return;
    }
    locationsStatus.textContent = 'Searching...';
    locationsResults.innerHTML = '';
    try {
      const payload = await fetchJson(`/api/locations/search?q=${encodeURIComponent(q)}&limit=25`);
      if (!payload.length) {
        locationsStatus.textContent = 'No locations found.';
        return;
      }
      locationsStatus.textContent = '';
      locationsResults.innerHTML = payload.map(loc => `
        <article class="card">
          <span class="card-id">${escapeHtml(loc.location_id)}</span>
          <h3>${escapeHtml(loc.display_name)}</h3>
          <p class="meta">${escapeHtml(loc.canonical_name)}</p>
          <p><strong>Type:</strong> ${escapeHtml(loc.location_type)}</p>
          <p><strong>Coords:</strong> ${loc.latitude}, ${loc.longitude}</p>
          <p class="meta">Confidence: ${loc.confidence_score}</p>
        </article>
      `).join('');
    } catch (err) {
      locationsStatus.textContent = 'Search failed — try again.';
    }
  });
}

// Events page
const eventsForm = document.getElementById('eventsSearchForm');
const eventsResults = document.getElementById('eventsResults');
const eventsStatus = document.getElementById('eventsStatus');

async function loadEvents(params = {}) {
  if (!eventsResults) return;
  eventsStatus.textContent = 'Loading...';
  eventsResults.innerHTML = '';
  const query = new URLSearchParams(params);
  try {
    const payload = await fetchJson(`/api/events?${query.toString()}`);
    const events = payload.events || [];
    if (!events.length) {
      eventsStatus.textContent = 'No events found.';
      return;
    }
    eventsStatus.textContent = '';
    eventsResults.innerHTML = events.map(event => `
      <article class="card">
        <span class="card-id">${escapeHtml(event.event_id)}</span>
        <h3>${escapeHtml(event.name || 'Event')}</h3>
        <p><strong>Type:</strong> ${escapeHtml(event.event_type)}</p>
        <p><strong>Timestamp:</strong> ${escapeHtml(event.event_timestamp || '—')}</p>
        <p class="meta">Person: ${escapeHtml(event.person_id || '—')} · Location: ${escapeHtml(event.location_id || '—')}</p>
        ${event.source_url ? `<p><a href="${event.source_url}" target="_blank">Source</a></p>` : ''}
      </article>
    `).join('');
  } catch (err) {
    eventsStatus.textContent = 'Failed to load events.';
  }
}

if (eventsForm) {
  eventsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const params = {
      person_id: document.getElementById('eventsPersonId')?.value.trim() || '',
      location_id: document.getElementById('eventsLocationId')?.value.trim() || '',
      event_type: document.getElementById('eventsType')?.value.trim() || '',
      start_date: document.getElementById('eventsStart')?.value || '',
      end_date: document.getElementById('eventsEnd')?.value || ''
    };
    Object.keys(params).forEach(key => { if (!params[key]) delete params[key]; });
    await loadEvents(params);
  });
  loadEvents();
}

// Sources page
const sourcesForm = document.getElementById('sourcesSearchForm');
const sourcesResults = document.getElementById('sourcesResults');
const sourcesStatus = document.getElementById('sourcesStatus');

async function loadSources(params = {}) {
  if (!sourcesResults) return;
  sourcesStatus.textContent = 'Loading...';
  sourcesResults.innerHTML = '';
  const query = new URLSearchParams(params);
  try {
    const payload = await fetchJson(`/api/sources?${query.toString()}`);
    const sources = payload.sources || [];
    if (!sources.length) {
      sourcesStatus.textContent = 'No sources found.';
      return;
    }
    sourcesStatus.textContent = '';
    sourcesResults.innerHTML = sources.map(source => `
      <article class="card">
        <span class="card-id">${escapeHtml(source.source_id)}</span>
        <h3>${escapeHtml(source.source_name)}</h3>
        <p><strong>Code:</strong> ${escapeHtml(source.source_code)}</p>
        <p><strong>Type:</strong> ${escapeHtml(source.source_type)} · ${escapeHtml(source.source_category)}</p>
        <p class="meta">Trust: ${escapeHtml(source.trust_tier)} · Verification: ${escapeHtml(source.verification_status)}</p>
        <p class="meta">Reliability: ${source.reliability_score ?? '—'}</p>
        ${source.source_url ? `<p><a href="${source.source_url}" target="_blank">Source URL</a></p>` : ''}
      </article>
    `).join('');
  } catch (err) {
    sourcesStatus.textContent = 'Failed to load sources.';
  }
}

if (sourcesForm) {
  sourcesForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const params = {
      source_type: document.getElementById('sourcesType')?.value.trim() || '',
      source_category: document.getElementById('sourcesCategory')?.value.trim() || '',
      trust_tier: document.getElementById('sourcesTrust')?.value.trim() || '',
      verification_status: document.getElementById('sourcesVerification')?.value.trim() || '',
      is_active: document.getElementById('sourcesActive')?.value || ''
    };
    Object.keys(params).forEach(key => { if (!params[key]) delete params[key]; });
    await loadSources(params);
  });
  loadSources({ is_active: 'true' });
}

// Person detail page
const personDetailEl = document.getElementById('personDetail');
const personStatusEl = document.getElementById('personStatus');

async function loadPersonDetail() {
  if (!personDetailEl) return;
  const id = new URLSearchParams(window.location.search).get('id');
  if (!id) {
    personStatusEl.textContent = 'No person id provided.';
    return;
  }
  personStatusEl.textContent = 'Loading...';
  try {
    const locationsPayload = await fetchJson(`/api/persons/${encodeURIComponent(id)}/locations`);
    const timelinePayload = await fetchJson(`/api/events/person/${encodeURIComponent(id)}/timeline`);
    const person = locationsPayload.person || {};
    const locations = locationsPayload.locations || [];
    const timeline = timelinePayload.timeline || [];

    personDetailEl.innerHTML = `
      <div class="card">
        <span class="card-id">${escapeHtml(person.pfif_id || id)}</span>
        <h2>${escapeHtml(person.given_name || '')} ${escapeHtml(person.family_name || '')}</h2>
      </div>
      <p><strong>Status:</strong> ${escapeHtml(person.status || '—')}</p>
      <p><strong>Age at disappearance:</strong> ${person.age_at_disappearance ?? '—'}</p>
      <p><strong>Last seen:</strong> ${escapeHtml(person.date_last_seen || '—')}</p>
      <p class="meta">Source: ${escapeHtml(person.primary_source || 'Unknown')}</p>
      <section class="detail-section">
        <h3>Locations</h3>
        ${locations.length ? locations.map(loc => `
          <div class="card">
            <p><strong>${escapeHtml(loc.display_name)}</strong></p>
            <p class="meta">${escapeHtml(loc.event_type)} · ${escapeHtml(loc.event_date || '—')}</p>
            <p>${escapeHtml(loc.event_description || '')}</p>
          </div>
        `).join('') : '<p class="meta">No location events.</p>'}
      </section>
      <section class="detail-section">
        <h3>Timeline</h3>
        ${timeline.length ? timeline.map(evt => `
          <div class="card">
            <p><strong>${escapeHtml(evt.name || evt.event_type)}</strong></p>
            <p class="meta">${escapeHtml(evt.event_type)} · ${escapeHtml(evt.event_timestamp || '—')}</p>
            <p>${evt.location_id ? `Location: ${escapeHtml(evt.location_id)}` : ''}</p>
          </div>
        `).join('') : '<p class="meta">No timeline events.</p>'}
      </section>
    `;
    personStatusEl.textContent = '';
  } catch (err) {
    personStatusEl.textContent = 'Failed to load person details.';
  }
}

loadPersonDetail();

// Admin forms for CRUD
const personLocationForm = document.getElementById('personLocationForm');
const personLocationStatus = document.getElementById('personLocationStatus');
if (personLocationForm) {
  personLocationForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    personLocationStatus.textContent = 'Adding location...';
    try {
      const pfif = document.getElementById('personLocationPfif').value.trim();
      const payload = {
        text: document.getElementById('personLocationText').value.trim(),
        event_type: document.getElementById('personLocationType').value.trim() || 'sighting',
        event_date: document.getElementById('personLocationDate').value || null,
        event_description: document.getElementById('personLocationDesc').value.trim() || null,
        source_url: document.getElementById('personLocationSource').value.trim() || null
      };
      await fetchJson(`/api/persons/${encodeURIComponent(pfif)}/locations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      personLocationStatus.textContent = 'Location added.';
      personLocationForm.reset();
    } catch (err) {
      personLocationStatus.textContent = 'Failed to add location.';
    }
  });
}

const eventCreateForm = document.getElementById('eventCreateForm');
const eventDeleteForm = document.getElementById('eventDeleteForm');
const eventStatus = document.getElementById('eventStatus');

if (eventCreateForm) {
  eventCreateForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    eventStatus.textContent = 'Creating event...';
    try {
      const payload = {
        name: document.getElementById('eventName').value.trim() || null,
        event_type: document.getElementById('eventType').value.trim(),
        event_timestamp: new Date(document.getElementById('eventTimestamp').value).toISOString(),
        person_id: document.getElementById('eventPersonId').value.trim() || null,
        location_id: document.getElementById('eventLocationId').value.trim() || null,
        source_url: document.getElementById('eventSourceUrl').value.trim() || null,
        confidence_score: document.getElementById('eventConfidence').value,
        is_public: document.getElementById('eventVisibility').value
      };
      await fetchJson('/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      eventStatus.textContent = 'Event created.';
      eventCreateForm.reset();
    } catch (err) {
      eventStatus.textContent = 'Failed to create event.';
    }
  });
}

if (eventDeleteForm) {
  eventDeleteForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    eventStatus.textContent = 'Deleting event...';
    try {
      const eventId = document.getElementById('eventDeleteId').value.trim();
      await fetchJson(`/api/events/${encodeURIComponent(eventId)}`, {
        method: 'DELETE',
        headers: { ...getAuthHeaders() }
      });
      eventStatus.textContent = 'Event deleted (soft).';
      eventDeleteForm.reset();
    } catch (err) {
      eventStatus.textContent = 'Failed to delete event.';
    }
  });
}

const sourceCreateForm = document.getElementById('sourceCreateForm');
const sourceDeleteForm = document.getElementById('sourceDeleteForm');
const sourceStatus = document.getElementById('sourceStatus');

if (sourceCreateForm) {
  sourceCreateForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    sourceStatus.textContent = 'Creating source...';
    try {
      const dataTypes = document.getElementById('sourceDataTypes').value
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);
      const payload = {
        source_name: document.getElementById('sourceName').value.trim(),
        source_code: document.getElementById('sourceCode').value.trim(),
        source_type: document.getElementById('sourceType').value.trim(),
        source_category: document.getElementById('sourceCategory').value.trim(),
        source_url: document.getElementById('sourceUrl').value.trim() || null,
        trust_tier: document.getElementById('sourceTrust').value.trim() || 'standard',
        verification_status: document.getElementById('sourceVerification').value.trim() || 'unverified',
        reliability_score: parseFloat(document.getElementById('sourceReliability').value || '0.7'),
        data_types: dataTypes.length ? dataTypes : null
      };
      await fetchJson('/api/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      sourceStatus.textContent = 'Source created.';
      sourceCreateForm.reset();
    } catch (err) {
      sourceStatus.textContent = 'Failed to create source.';
    }
  });
}

if (sourceDeleteForm) {
  sourceDeleteForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    sourceStatus.textContent = 'Deleting source...';
    try {
      const sourceId = document.getElementById('sourceDeleteId').value.trim();
      await fetchJson(`/api/sources/${encodeURIComponent(sourceId)}`, {
        method: 'DELETE',
        headers: { ...getAuthHeaders() }
      });
      sourceStatus.textContent = 'Source deleted.';
      sourceDeleteForm.reset();
    } catch (err) {
      sourceStatus.textContent = 'Failed to delete source.';
    }
  });
}

// Person CRUD
const personCreateForm = document.getElementById('personCreateForm');
const personUpdateForm = document.getElementById('personUpdateForm');
const personDeleteForm = document.getElementById('personDeleteForm');
const personStatusMsg = document.getElementById('personStatusMsg');

if (personCreateForm) {
  personCreateForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    personStatusMsg.textContent = 'Creating person...';
    try {
      const payload = {
        pfif_id: document.getElementById('personPfif').value.trim(),
        given_name: document.getElementById('personGiven').value.trim() || null,
        family_name: document.getElementById('personFamily').value.trim() || null,
        age_at_disappearance: parseInt(document.getElementById('personAge').value || '', 10) || null,
        sex: document.getElementById('personSex').value.trim() || null,
        status: document.getElementById('personStatus').value.trim() || 'missing',
        date_last_seen: document.getElementById('personLastSeen').value || null,
        primary_source: document.getElementById('personSource').value.trim() || null,
        source_url: document.getElementById('personSourceUrl').value.trim() || null
      };
      await fetchJson('/api/persons', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      personStatusMsg.textContent = 'Person created.';
      personCreateForm.reset();
    } catch (err) {
      personStatusMsg.textContent = 'Failed to create person.';
    }
  });
}

if (personUpdateForm) {
  personUpdateForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    personStatusMsg.textContent = 'Updating person...';
    try {
      const pfif = document.getElementById('personUpdatePfif').value.trim();
      const confirmed = document.getElementById('personUpdateConfirmed').value;
      const payload = {
        given_name: document.getElementById('personUpdateGiven').value.trim() || undefined,
        family_name: document.getElementById('personUpdateFamily').value.trim() || undefined,
        status: document.getElementById('personUpdateStatus').value.trim() || undefined,
        is_confirmed: confirmed === '' ? undefined : confirmed === 'true'
      };
      Object.keys(payload).forEach(key => payload[key] === undefined && delete payload[key]);
      await fetchJson(`/api/persons/${encodeURIComponent(pfif)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      personStatusMsg.textContent = 'Person updated.';
      personUpdateForm.reset();
    } catch (err) {
      personStatusMsg.textContent = 'Failed to update person.';
    }
  });
}

if (personDeleteForm) {
  personDeleteForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    personStatusMsg.textContent = 'Deleting person...';
    try {
      const pfif = document.getElementById('personDeletePfif').value.trim();
      await fetchJson(`/api/persons/${encodeURIComponent(pfif)}`, {
        method: 'DELETE',
        headers: { ...getAuthHeaders() }
      });
      personStatusMsg.textContent = 'Person deleted (soft).';
      personDeleteForm.reset();
    } catch (err) {
      personStatusMsg.textContent = 'Failed to delete person.';
    }
  });
}

// Location CRUD
const locationCreateForm = document.getElementById('locationCreateForm');
const locationUpdateForm = document.getElementById('locationUpdateForm');
const locationDeleteForm = document.getElementById('locationDeleteForm');
const locationStatusMsg = document.getElementById('locationStatusMsg');

if (locationCreateForm) {
  locationCreateForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    locationStatusMsg.textContent = 'Creating location...';
    try {
      const payload = {
        location_id: document.getElementById('locationId').value.trim(),
        display_name: document.getElementById('locationDisplay').value.trim(),
        canonical_name: document.getElementById('locationCanonical').value.trim(),
        latitude: parseFloat(document.getElementById('locationLat').value),
        longitude: parseFloat(document.getElementById('locationLng').value),
        country_code: document.getElementById('locationCountryCode').value.trim(),
        country_name: document.getElementById('locationCountryName').value.trim(),
        admin1_name: document.getElementById('locationAdmin1').value.trim() || null,
        locality: document.getElementById('locationLocality').value.trim() || null,
        location_type: document.getElementById('locationType').value.trim()
      };
      await fetchJson('/api/locations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      locationStatusMsg.textContent = 'Location created.';
      locationCreateForm.reset();
    } catch (err) {
      locationStatusMsg.textContent = 'Failed to create location.';
    }
  });
}

if (locationUpdateForm) {
  locationUpdateForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    locationStatusMsg.textContent = 'Updating location...';
    try {
      const locationId = document.getElementById('locationUpdateId').value.trim();
      const activeValue = document.getElementById('locationUpdateActive').value;
      const payload = {
        display_name: document.getElementById('locationUpdateDisplay').value.trim() || undefined,
        canonical_name: document.getElementById('locationUpdateCanonical').value.trim() || undefined,
        latitude: document.getElementById('locationUpdateLat').value ? parseFloat(document.getElementById('locationUpdateLat').value) : undefined,
        longitude: document.getElementById('locationUpdateLng').value ? parseFloat(document.getElementById('locationUpdateLng').value) : undefined,
        is_active: activeValue === '' ? undefined : activeValue === 'true'
      };
      Object.keys(payload).forEach(key => payload[key] === undefined && delete payload[key]);
      await fetchJson(`/api/locations/${encodeURIComponent(locationId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      locationStatusMsg.textContent = 'Location updated.';
      locationUpdateForm.reset();
    } catch (err) {
      locationStatusMsg.textContent = 'Failed to update location.';
    }
  });
}

if (locationDeleteForm) {
  locationDeleteForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    locationStatusMsg.textContent = 'Deleting location...';
    try {
      const locationId = document.getElementById('locationDeleteId').value.trim();
      await fetchJson(`/api/locations/${encodeURIComponent(locationId)}`, {
        method: 'DELETE',
        headers: { ...getAuthHeaders() }
      });
      locationStatusMsg.textContent = 'Location deleted (soft).';
      locationDeleteForm.reset();
    } catch (err) {
      locationStatusMsg.textContent = 'Failed to delete location.';
    }
  });
}
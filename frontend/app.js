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

// Suggestion links
const suggestionLinks = document.querySelectorAll('.suggestion-link');
suggestionLinks.forEach(link => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    const query = link.getAttribute('data-query');
    if (!query) return;

    // If the app is opened via file:// or origin is null, do a navigation to persons page
    // so that the request uses HTTP rather than being a blocked file:// fetch
    const origin = window.location && window.location.origin ? window.location.origin : '';
    const isLocalFile = window.location.protocol === 'file:' || origin === 'null' || origin === '';
    if (isLocalFile) {
      // Navigate to persons page with query in URL so that persons.html will run the search on load
      window.location.href = `persons.html?q=${encodeURIComponent(query)}`;
      return;
    }

    // Otherwise just fill the search input and trigger the in-page AJAX search
    if (queryInput) {
      queryInput.value = query;
      if (form) {
        form.dispatchEvent(new Event('submit'));
      }
    }
  });
});

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

// ID generation utilities
function generatePersonId(givenName, familyName, source = 'manual') {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 6).toUpperCase();
  const name = (familyName || givenName || 'unknown').toLowerCase().replace(/[^a-z0-9]/g, '');
  return `opentrace.org/person.${source}.PER-${name}-${timestamp}-${random}`;
}

function generateLocationId(displayName) {
  const slug = displayName
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .substring(0, 50);
  return `LOC-${slug}`;
}

function generateEventId() {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 10).toUpperCase();
  return `EV-${timestamp}-${random}`;
}

function generateSourceId() {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8).toUpperCase();
  return `SRC-${timestamp}-${random}`;
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
  const pfifId = p.pfif_id || p.id || '';  // Use id as fallback for data attribute
  
  return `
    <div class="card">
      <span class="card-id">${escapeHtml(id)}</span>
      <h4>${escapeHtml(p.given_name || '')} ${escapeHtml(p.family_name || '')}</h4>
      <p>${escapeHtml(location)} — ${escapeHtml(author)}</p>
      <p>
    <button data-pfif="${encodeURIComponent(pfifId)}" class="approve">Approve</button>
    <button data-pfif="${encodeURIComponent(pfifId)}" class="danger delete-profile" style="margin-left:8px;">Delete</button>
  </p>
    </div>
  `;
}

if (profilesEl) {
  profilesEl.addEventListener('click', async (e) => {
    // Approve handler
    if (e.target.classList.contains('approve')) {
      const pfif = decodeURIComponent(e.target.dataset.pfif);
      
      if (!token) {
        alert('Not authenticated. Please log in first.');
        return;
      }
      
      e.target.disabled = true;
      e.target.textContent = 'Approving...';
      
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
        
        if (!res.ok && res.status !== 404) {
          throw new Error(`Approve failed: ${res.status}`);
        }
        
        if (!res.ok || res.status === 404) {
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
        
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`Approve failed: ${res.status} - ${errText}`);
        }
        
        const result = await res.json();
        console.log('Approve success:', result);
        
        // Reload the list
        await loadUnconfirmed();
      } catch (err) {
        console.error('Approve error:', err);
        if (loginStatus) loginStatus.textContent = `Approve failed: ${err.message}`;
        e.target.disabled = false;
        e.target.textContent = 'Approve';
      }
      return;
    }

    // Delete handler for profile rows
    if (e.target.classList.contains('delete-profile')) {
      const pfif = decodeURIComponent(e.target.dataset.pfif);
      if (!confirm('Are you sure you want to remove this profile permanently? This will also remove related data.')) return;
      if (!token) {
        alert('Not authenticated. Please log in first.');
        return;
      }

      try {
        // Try deleting from new Person table first (soft delete)
        let res = await fetch(`/api/persons/${encodeURIComponent(pfif)}`, {
          method: 'DELETE',
          headers: { 'Authorization': 'Bearer ' + token }
        });
        if (res.ok) {
          alert('Person deleted (soft)');
          await loadUnconfirmed();
          return;
        }
        // If not found on Person table, use takedown for PersonProfile
        res = await fetch('/admin/takedown', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
          body: JSON.stringify({ pfif_id: pfif })
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`${res.status}: ${errText}`);
        }
        alert('Profile removed');
        await loadUnconfirmed();
      } catch (err) {
        console.error('Delete profile error:', err);
        alert(`Delete failed: ${err.message}`);
      }
      return;
    }

  });
}

// Admin entity management
const loadPersonsBtn = document.getElementById('loadPersonsBtn');
const loadLocationsBtn = document.getElementById('loadLocationsBtn');
const loadEventsBtn = document.getElementById('loadEventsBtn');
const loadSourcesBtn = document.getElementById('loadSourcesBtn');
const adminPersonsList = document.getElementById('adminPersonsList');
const adminLocationsList = document.getElementById('adminLocationsList');
const adminEventsList = document.getElementById('adminEventsList');
const adminSourcesList = document.getElementById('adminSourcesList');

// Show unconfirmed toggles
const showUnconfirmedPersons = document.getElementById('showUnconfirmedPersons');
const showUnconfirmedLocations = document.getElementById('showUnconfirmedLocations');
const showUnconfirmedEvents = document.getElementById('showUnconfirmedEvents');
const showUnconfirmedSources = document.getElementById('showUnconfirmedSources');

// Re-load lists when toggles change
if (showUnconfirmedPersons) showUnconfirmedPersons.addEventListener('change', () => { if (loadPersonsBtn) loadPersonsBtn.click(); });
if (showUnconfirmedLocations) showUnconfirmedLocations.addEventListener('change', () => { if (loadLocationsBtn) loadLocationsBtn.click(); });
if (showUnconfirmedEvents) showUnconfirmedEvents.addEventListener('change', () => { if (loadEventsBtn) loadEventsBtn.click(); });
if (showUnconfirmedSources) showUnconfirmedSources.addEventListener('change', () => { if (loadSourcesBtn) loadSourcesBtn.click(); });

if (loadPersonsBtn) {
  loadPersonsBtn.addEventListener('click', async () => {
    adminPersonsList.innerHTML = 'Loading...';
    try {
      const payload = await fetchJson('/admin/all-persons?limit=100', {
        headers: getAuthHeaders()
      });
      const persons = payload.persons || [];
      // Filter by confirmed status based on checkbox
      const showUnconfirmed = document.getElementById('showUnconfirmedPersons')?.checked;
      const filteredPersons = persons.filter(p => {
        if (p.is_active === false) return false; // Never show inactive
        if (showUnconfirmed) return true; // Show all if checked
        return p.is_confirmed === true; // Show only confirmed by default
      });
      if (!filteredPersons.length) {
        adminPersonsList.innerHTML = '<em>No persons found</em>';
        return;
      }
      adminPersonsList.innerHTML = filteredPersons.map(p => `
        <div class="card">
          <div class="card-left">
            <span class="card-id">${escapeHtml(p.pfif_id)}</span>
            <h4>${escapeHtml(p.given_name || '')} ${escapeHtml(p.family_name || '')}</h4>
            <p class="meta">Status: ${escapeHtml(p.status)} | Confirmed: ${p.is_confirmed ? 'Yes' : 'No'}</p>
          </div>
          <div class="card-actions">
            <a href="/profile.html?id=${encodeURIComponent(p.pfif_id)}" target="_blank">View</a> |
            <button class="danger delete-person" data-pfif="${encodeURIComponent(p.pfif_id)}">Delete</button>
          </div>
        </div>
      `).join('');
    } catch (err) {
      console.error('Load persons error:', err);
      adminPersonsList.innerHTML = '<em>Failed to load persons</em>';
    }
  });
}

if (loadLocationsBtn) {
  loadLocationsBtn.addEventListener('click', async () => {
    adminLocationsList.innerHTML = 'Loading...';
    try {
      const payload = await fetchJson('/api/locations?limit=100', {
        headers: getAuthHeaders()
      });
      const locations = payload.locations || payload || [];
      // Filter by confirmed status based on checkbox
      const showUnconfirmed = document.getElementById('showUnconfirmedLocations')?.checked;
      const filteredLocations = locations.filter(loc => {
        if (loc.is_active === false) return false;
        if (showUnconfirmed) return true;
        return loc.is_confirmed !== false; // Locations may not have is_confirmed field
      });
      if (!filteredLocations.length) {
        adminLocationsList.innerHTML = '<em>No locations found</em>';
        return;
      }
      adminLocationsList.innerHTML = filteredLocations.map(loc => `
        <div class="card">
          <div class="card-left">
            <span class="card-id">${escapeHtml(loc.location_id)}</span>
            <h4>${escapeHtml(loc.display_name)}</h4>
            <p class="meta">${escapeHtml(loc.canonical_name)}</p>
          </div>
          <div class="card-actions">
            <a href="/location-detail.html?id=${encodeURIComponent(loc.location_id)}" target="_blank">View</a> |
            <button class="danger delete-location" data-id="${encodeURIComponent(loc.location_id)}">Delete</button>
          </div>
        </div>
      `).join('');
    } catch (err) {
      adminLocationsList.innerHTML = '<em>Failed to load locations</em>';
    }
  });
}

if (loadEventsBtn) {
  loadEventsBtn.addEventListener('click', async () => {
    adminEventsList.innerHTML = 'Loading...';
    try {
      const payload = await fetchJson('/api/events?limit=100', {
        headers: getAuthHeaders()
      });
      const events = payload.events || [];
      // Filter by confirmed status based on checkbox
      const showUnconfirmed = document.getElementById('showUnconfirmedEvents')?.checked;
      const filteredEvents = events.filter(evt => {
        if (evt.is_active === false) return false;
        if (showUnconfirmed) return true;
        return evt.is_confirmed !== false;
      });
      if (!filteredEvents.length) {
        adminEventsList.innerHTML = '<em>No events found</em>';
        return;
      }
      adminEventsList.innerHTML = filteredEvents.map(evt => `
        <div class="card">
          <div class="card-left">
            <span class="card-id">${escapeHtml(evt.event_id)}</span>
            <h4>${escapeHtml(evt.name || evt.event_type)}</h4>
            <p class="meta">${escapeHtml(evt.event_timestamp || '')}</p>
          </div>
          <div class="card-actions">
            <a href="/event-detail.html?id=${encodeURIComponent(evt.event_id)}" target="_blank">View</a> |
            <button class="danger delete-event" data-id="${encodeURIComponent(evt.event_id)}">Delete</button>
          </div>
        </div>
      `).join('');
    } catch (err) {
      adminEventsList.innerHTML = '<em>Failed to load events</em>';
    }
  });
}

if (loadSourcesBtn) {
  loadSourcesBtn.addEventListener('click', async () => {
    adminSourcesList.innerHTML = 'Loading...';
    try {
      const payload = await fetchJson('/api/sources?limit=100', {
        headers: getAuthHeaders()
      });
      const sources = payload.sources || [];
      // Filter by confirmed status based on checkbox
      const showUnconfirmed = document.getElementById('showUnconfirmedSources')?.checked;
      const filteredSources = sources.filter(src => {
        if (src.is_active === false) return false;
        if (showUnconfirmed) return true;
        return src.is_confirmed !== false;
      });
      if (!filteredSources.length) {
        adminSourcesList.innerHTML = '<em>No sources found</em>';
        return;
      }
      adminSourcesList.innerHTML = filteredSources.map(src => `
        <div class="card">
          <div class="card-left">
            <span class="card-id">${escapeHtml(src.source_id)}</span>
            <h4>${escapeHtml(src.source_name)}</h4>
            <p class="meta">${escapeHtml(src.source_type)} | ${escapeHtml(src.source_category)}</p>
          </div>
          <div class="card-actions">
            <button class="danger delete-source" data-id="${encodeURIComponent(src.source_id)}">Delete</button>
          </div>
        </div>
      `).join('');
    } catch (err) {
      adminSourcesList.innerHTML = '<em>Failed to load sources</em>';
    }
  });
}

// Delete handlers
document.addEventListener('click', async (e) => {
  if (e.target.classList.contains('delete-person')) {
    if (!confirm('Are you sure you want to delete this person? This action cannot be undone.')) return;
    const pfif = decodeURIComponent(e.target.dataset.pfif);
    try {
      const res = await fetch(`/api/persons/${encodeURIComponent(pfif)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`${res.status}: ${errorText}`);
      }
      alert('Person deleted successfully');
      loadPersonsBtn.click();
    } catch (err) {
      console.error('Delete person error:', err);
      alert(`Delete failed: ${err.message}`);
    }
  }
  
  if (e.target.classList.contains('delete-location')) {
    if (!confirm('Are you sure you want to delete this location?')) return;
    const id = decodeURIComponent(e.target.dataset.id);
    try {
      const res = await fetch(`/api/locations/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`${res.status}: ${errorText}`);
      }
      alert('Location deleted successfully');
      loadLocationsBtn.click();
    } catch (err) {
      console.error('Delete location error:', err);
      alert(`Delete failed: ${err.message}`);
    }
  }
  
  if (e.target.classList.contains('delete-event')) {
    if (!confirm('Are you sure you want to delete this event?')) return;
    const id = decodeURIComponent(e.target.dataset.id);
    try {
      const res = await fetch(`/api/events/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`${res.status}: ${errorText}`);
      }
      alert('Event deleted successfully');
      loadEventsBtn.click();
    } catch (err) {
      console.error('Delete event error:', err);
      alert(`Delete failed: ${err.message}`);
    }
  }
  
  if (e.target.classList.contains('delete-source')) {
    if (!confirm('Are you sure you want to delete this source?')) return;
    const id = decodeURIComponent(e.target.dataset.id);
    try {
      const res = await fetch(`/api/sources/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`${res.status}: ${errorText}`);
      }
      alert('Source deleted successfully');
      loadSourcesBtn.click();
    } catch (err) {
      console.error('Delete source error:', err);
      alert(`Delete failed: ${err.message}`);
    }
  }
});

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
      let url;
      if (q || location) {
        // Use search endpoint with parameters
        url = `/search?q=${encodeURIComponent(q)}&location=${encodeURIComponent(location)}`;
      } else {
        // Use persons list endpoint for browsing
        url = '/api/persons?limit=50';
      }
      const payload = await fetchJson(url);
      const items = Array.isArray(payload) ? payload : (payload.results || payload.persons || []);
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
  // Only auto-submit if there's a query parameter (e.g., from search from home page)
  if (params.get('q')) {
    personsForm.dispatchEvent(new Event('submit'));
  }
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
      locationsResults.innerHTML = payload.map(loc => {
        const locId = encodeURIComponent(loc.location_id);
        return `
          <article class="card">
            <span class="card-id">${escapeHtml(loc.location_id)}</span>
            <h3>${escapeHtml(loc.display_name)}</h3>
            <p class="meta">${escapeHtml(loc.canonical_name)}</p>
            <p><strong>Type:</strong> ${escapeHtml(loc.location_type)}</p>
            <p><strong>Coords:</strong> ${loc.latitude}, ${loc.longitude}</p>
            <p class="meta">Confidence: ${loc.confidence_score}</p>
            <p><a href="/location-detail.html?id=${locId}">View details</a></p>
          </article>
        `;
      }).join('');
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
    eventsResults.innerHTML = events.map(event => {
      const eventId = encodeURIComponent(event.event_id);
      return `
        <article class="card">
          <span class="card-id">${escapeHtml(event.event_id)}</span>
          <h3>${escapeHtml(event.name || 'Event')}</h3>
          <p><strong>Type:</strong> ${escapeHtml(event.event_type)}</p>
          <p><strong>Timestamp:</strong> ${escapeHtml(event.event_timestamp || '—')}</p>
          <p class="meta">Person: ${escapeHtml(event.person_id || '—')} · Location: ${escapeHtml(event.location_id || '—')}</p>
          <p><a href="/event-detail.html?id=${eventId}">View details</a></p>
          ${event.source_url ? `<p><a href="${event.source_url}" target="_blank">Source</a></p>` : ''}
        </article>
      `;
    }).join('');
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
const personIdEl = document.getElementById('personId');
const personNameEl = document.getElementById('personName');

async function loadPersonDetail() {
  if (!personDetailEl) return;
  const id = new URLSearchParams(window.location.search).get('id');
  if (!id) {
    personStatusEl.textContent = 'No person id provided.';
    return;
  }
  personStatusEl.textContent = 'Loading...';
  try {
    // Try to fetch person details (works for both confirmed and unconfirmed if admin)
    const token = sessionStorage.getItem('opentrace_token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
    const personPayload = await fetchJson(`/api/persons/${encodeURIComponent(id)}`, { headers });
    const person = personPayload.person || {};
    
    // Show name and ID in header
    let personName = `${person.given_name || ''} ${person.family_name || ''}`.trim() || 'Unnamed Person';
    // Normalize whitespace and remove zero-width characters so letters don't stack vertically
    personName = personName.replace(/\u200B/g, '').replace(/\s+/g, ' ').trim();
    if (personNameEl) {
      personNameEl.textContent = personName;
    }
    if (personIdEl) {
      personIdEl.textContent = escapeHtml(person.pfif_id || id);
    }

    // Try to fetch locations and events (these might fail if person has none)
    let locations = [];
    let timeline = [];
    try {
      const locPayload = await fetchJson(`/api/locations?person_id=${encodeURIComponent(id)}`, { headers });
      locations = locPayload.locations || [];
    } catch (e) {
      console.log('No locations found');
    }
    
    try {
      const evtPayload = await fetchJson(`/api/events?person_id=${encodeURIComponent(id)}`, { headers });
      timeline = evtPayload.events || [];
    } catch (e) {
      console.log('No events found');
    }

    const confirmedBadge = person.is_confirmed ? '' : '<span style="background: #f59e0b; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.9rem; margin-left: 1rem;">Unconfirmed</span>';

    personDetailEl.innerHTML = `
      <div class="card">
        <span class="card-id">${escapeHtml(person.pfif_id || id)}</span>
        <h2>${escapeHtml(person.given_name || '')} ${escapeHtml(person.family_name || '')}${confirmedBadge}</h2>
      </div>
      <p><strong>Status:</strong> ${escapeHtml(person.status || '—')}</p>
      <p><strong>Age at disappearance:</strong> ${person.age_at_disappearance ?? '—'}</p>
      <p><strong>Sex:</strong> ${escapeHtml(person.sex || '—')}</p>
      <p><strong>Last seen:</strong> ${escapeHtml(person.date_last_seen || '—')}</p>
      <p><strong>Source:</strong> ${person.source_url ? `<a href="${escapeHtml(person.source_url)}" target="_blank">${escapeHtml(person.primary_source || 'View Source')}</a>` : escapeHtml(person.primary_source || 'Unknown')}</p>
      ${person.alternate_names && person.alternate_names.length ? `<p><strong>Alternate names:</strong> ${person.alternate_names.map(escapeHtml).join(', ')}</p>` : ''}
      <section class="detail-section">
        <h3>Locations</h3>
        ${locations.length ? locations.map(loc => `
          <div class="card">
            <p><strong>${escapeHtml(loc.display_name)}</strong></p>
            <p class="meta">${escapeHtml(loc.canonical_name || '')}</p>
          </div>
        `).join('') : '<p class="meta">No locations recorded.</p>'}
      </section>
      <section class="detail-section">
        <h3>Timeline</h3>
        ${timeline.length ? timeline.map(evt => `
          <div class="card">
            <p><strong>${escapeHtml(evt.name || evt.event_type)}</strong></p>
            <p class="meta">${escapeHtml(evt.event_timestamp || '—')}</p>
            <p>${escapeHtml(evt.description || '')}</p>
          </div>
        `).join('') : '<p class="meta">No timeline events.</p>'}
      </section>
    `;
    personStatusEl.textContent = '';
  } catch (err) {
    console.error('Failed to load person:', err);
    personStatusEl.textContent = 'Failed to load person details. This person may not be confirmed yet or may have been deleted.';
  }
}

loadPersonDetail();

// Location detail page
const locationDetailEl = document.getElementById('locationDetail');
const locationStatusEl = document.getElementById('locationStatus');
const locationIdEl = document.getElementById('locationId');
const locationNameEl = document.getElementById('locationName');

async function loadLocationDetail() {
  if (!locationDetailEl) return;
  const id = new URLSearchParams(window.location.search).get('id');
  if (!id) {
    locationStatusEl.textContent = 'No location id provided.';
    return;
  }
  locationStatusEl.textContent = 'Loading...';
  try {
    const payload = await fetchJson(`/api/locations/${encodeURIComponent(id)}`);
    const location = payload || {};
    
    // Show name and ID in header
    if (locationNameEl) {
      locationNameEl.textContent = location.display_name || 'Unknown Location';
    }
    if (locationIdEl) {
      locationIdEl.textContent = escapeHtml(location.location_id || id);
    }

    locationDetailEl.innerHTML = `
      <div class="card">
        <h2>${escapeHtml(location.display_name || 'Location')}</h2>
      </div>
      <p><strong>Canonical Name:</strong> ${escapeHtml(location.canonical_name || '—')}</p>
      <p><strong>Type:</strong> ${escapeHtml(location.location_type || '—')}</p>
      <p><strong>Coordinates:</strong> ${location.latitude ?? '—'}, ${location.longitude ?? '—'}</p>
      <p><strong>Country:</strong> ${escapeHtml(location.country_name || '—')} (${escapeHtml(location.country_code || '—')})</p>
      <p><strong>Admin1 (State/Province):</strong> ${escapeHtml(location.admin1_name || '—')}</p>
      <p><strong>Locality (City):</strong> ${escapeHtml(location.locality || '—')}</p>
      <p class="meta">Confidence: ${location.confidence_score ?? '—'}</p>
    `;
    locationStatusEl.textContent = '';
  } catch (err) {
    locationStatusEl.textContent = 'Failed to load location details.';
  }
}

loadLocationDetail();

// Event detail page
const eventDetailEl = document.getElementById('eventDetail');
const eventStatusEl = document.getElementById('eventStatus');
const eventIdEl = document.getElementById('eventId');
const eventNameEl = document.getElementById('eventName');

async function loadEventDetail() {
  if (!eventDetailEl) return;
  const id = new URLSearchParams(window.location.search).get('id');
  if (!id) {
    eventStatusEl.textContent = 'No event id provided.';
    return;
  }
  eventStatusEl.textContent = 'Loading...';
  try {
    const payload = await fetchJson(`/api/events/${encodeURIComponent(id)}`);
    const event = payload || {};
    
    // Show name and ID in header
    if (eventNameEl) {
      eventNameEl.textContent = event.name || event.event_type || 'Event';
    }
    if (eventIdEl) {
      eventIdEl.textContent = escapeHtml(event.event_id || id);
    }

    eventDetailEl.innerHTML = `
      <div class="card">
        <h2>${escapeHtml(event.name || event.event_type || 'Event')}</h2>
      </div>
      <p><strong>Type:</strong> ${escapeHtml(event.event_type || '—')}</p>
      <p><strong>Timestamp:</strong> ${escapeHtml(event.event_timestamp || '—')}</p>
      <p><strong>Person:</strong> ${escapeHtml(event.person_id || '—')}</p>
      <p><strong>Location:</strong> ${escapeHtml(event.location_id || '—')}</p>
      <p><strong>Confidence:</strong> ${escapeHtml(event.confidence || '—')}</p>
      <p><strong>Visibility:</strong> ${escapeHtml(event.visibility || '—')}</p>
      <p>${escapeHtml(event.description || '')}</p>
      ${event.source_url ? `<p><a href="${event.source_url}" target="_blank">Source</a></p>` : ''}
    `;
    eventStatusEl.textContent = '';
  } catch (err) {
    eventStatusEl.textContent = 'Failed to load event details.';
  }
}

loadEventDetail();

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
      const payload = {        event_id: generateEventId(),        name: document.getElementById('eventName').value.trim() || null,
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
        source_id: generateSourceId(),
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

// NamUs scraper admin actions
const urlScrapeForm = document.getElementById('urlScrapeForm');
const urlStatus = document.getElementById('urlStatus');

if (urlScrapeForm) {
  urlScrapeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    urlStatus.textContent = 'Scraping URL...';
    try {
      const url = document.getElementById('urlInput').value.trim();
      const payload = { url: url };
      const res = await fetchJson('/admin/scrape/url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      
      if (res.found) {
        urlStatus.textContent = `✅ ${res.message}${res.created ? ' (New record created)' : ' (Already exists)'}`;
        if (res.person) {
          urlStatus.textContent += ` - ${res.person.given_name || ''} ${res.person.family_name || ''}`;
        }
      } else {
        urlStatus.textContent = `⚠️ ${res.message}`;
      }
      
      urlScrapeForm.reset();
    } catch (err) {
      urlStatus.textContent = `❌ Scraping failed: ${err.message}`;
    }
  });
}

// Generic URL scraper admin actions
const genericUrlScrapeForm = document.getElementById('genericUrlScrapeForm');
const genericUrlStatus = document.getElementById('genericUrlStatus');

if (genericUrlScrapeForm) {
  genericUrlScrapeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    genericUrlStatus.textContent = 'Scraping URL...';
    try {
      const url = document.getElementById('genericUrlInput').value.trim();
      const payload = { url: url };
      const res = await fetchJson('/admin/scrape/generic-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      
      if (res.found) {
        genericUrlStatus.textContent = `✅ ${res.message}${res.created ? ' (New record created)' : ' (Already exists)'}`;
        if (res.person) {
          genericUrlStatus.textContent += ` - ${res.person.given_name || ''} ${res.person.family_name || ''}`;
        }
      } else {
        genericUrlStatus.textContent = `⚠️ ${res.message}`;
      }
      
      genericUrlScrapeForm.reset();
    } catch (err) {
      genericUrlStatus.textContent = `❌ Scraping failed: ${err.message}`;
    }
  });
}

// PDF scraper admin actions
const pdfScrapeForm = document.getElementById('pdfScrapeForm');
const pdfStatus = document.getElementById('pdfStatus');

if (pdfScrapeForm) {
  pdfScrapeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    pdfStatus.textContent = 'Processing PDF...';
    try {
      const fileInput = document.getElementById('pdfInput');
      const file = fileInput.files[0];
      
      if (!file) {
        pdfStatus.textContent = '❌ Please select a PDF file';
        return;
      }
      
      const formData = new FormData();
      formData.append('file', file);
      
      const res = await fetch('/admin/scrape/pdf', {
        method: 'POST',
        headers: { ...getAuthHeaders() },
        body: formData
      });
      
      const data = await res.json();
      
      if (res.ok && data.found) {
        pdfStatus.textContent = `✅ ${data.message}${data.created ? ' (New record created)' : ' (Already exists)'}`;
        if (data.person) {
          pdfStatus.textContent += ` - ${data.person.given_name || ''} ${data.person.family_name || ''}`;
        }
      } else {
        pdfStatus.textContent = `⚠️ ${data.message || 'Failed to process PDF'}`;
      }
      
      pdfScrapeForm.reset();
    } catch (err) {
      pdfStatus.textContent = `❌ Processing failed: ${err.message}`;
    }
  });
}

const namusScanForm = document.getElementById('namusScanForm');
const namusStatus = document.getElementById('namusStatus');

if (namusScrapeForm) {
  namusScrapeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    namusStatus.textContent = 'Scraping case...';
    try {
      const caseId = document.getElementById('namusCaseId').value.trim();
      const payload = { case_id: caseId };
      const res = await fetchJson('/admin/scrape/namus', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      namusStatus.textContent = res.found
        ? `Found: ${res.person?.pfif_id || caseId}`
        : res.message;
    } catch (err) {
      namusStatus.textContent = 'Scrape failed.';
    }
  });
}

if (namusScanForm) {
  namusScanForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    namusStatus.textContent = 'Scanning...';
    try {
      const startId = document.getElementById('namusStartId').value.trim();
      const maxChecks = parseInt(document.getElementById('namusMaxChecks').value, 10) || 5;
      const payload = { start_case_id: startId, max_checks: maxChecks };
      const res = await fetchJson('/admin/scrape/namus-until-found', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(payload)
      });
      namusStatus.textContent = res.found
        ? `Found: ${res.case_id}`
        : res.message;
    } catch (err) {
      namusStatus.textContent = 'Scan failed.';
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
      const givenName = document.getElementById('personGiven').value.trim() || null;
      const familyName = document.getElementById('personFamily').value.trim() || null;
      const primarySource = document.getElementById('personSource').value.trim() || 'manual';
      
      const payload = {
        pfif_id: generatePersonId(givenName, familyName, primarySource),
        given_name: givenName,
        family_name: familyName,
        age_at_disappearance: parseInt(document.getElementById('personAge').value || '', 10) || null,
        sex: document.getElementById('personSex').value.trim() || null,
        status: document.getElementById('personStatus').value.trim() || 'missing',
        date_last_seen: document.getElementById('personLastSeen').value || null,
        primary_source: primarySource,
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
      const displayName = document.getElementById('locationDisplay').value.trim();
      
      const payload = {
        location_id: generateLocationId(displayName),
        display_name: displayName,
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
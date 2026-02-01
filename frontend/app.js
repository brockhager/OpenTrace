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
let token = null;
const loginForm = document.getElementById('loginForm');
const loginStatus = document.getElementById('loginStatus');
const reviewSection = document.getElementById('reviewSection');
const profilesEl = document.getElementById('profiles');

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
      loginStatus.textContent = 'Signed in';
      document.getElementById('loginSection').style.display = 'none';
      reviewSection.style.display = 'block';
      await loadUnconfirmed();
    } catch (err) {
      loginStatus.textContent = 'Sign-in failed — check credentials';
    }
  });
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
  
  return `
    <div class="card">
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
const form = document.getElementById('searchForm');
const queryInput = document.getElementById('query');
const resultsEl = document.getElementById('results');
const statusEl = document.getElementById('status');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = queryInput.value.trim();
  if (!q) {
    statusEl.textContent = 'Please enter a search term.';
    return;
  }
  statusEl.textContent = 'Searching...';
  resultsEl.innerHTML = '';

  try {
    const res = await fetch(`/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error('Search failed');
    const payload = await res.json();
    const items = payload.results || [];
    if (items.length === 0) {
      statusEl.textContent = 'No results found.';
      return;
    }
    statusEl.textContent = '';
    resultsEl.innerHTML = items.map(p => renderCard(p)).join('');
  } catch (err) {
    statusEl.textContent = 'Search failed — try again.';
  }
});

function renderCard(p) {
  const name = `${p.given_name || ''} ${p.family_name || ''}`.trim() || 'Unnamed';
  const pfif = encodeURIComponent(p.pfif_id);
  return `
    <article class="card">
      <h3>${escapeHtml(name)} <span class="meta">(${p.age || '—'}, ${p.sex || '—'})</span></h3>
      <p><strong>Last seen:</strong> ${escapeHtml(p.last_seen_location || 'Unknown')}</p>
      <p><strong>Status:</strong> ${escapeHtml(p.status)}</p>
      <p class="meta">Source: ${escapeHtml(p.source || 'Unknown')}</p>
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

// Optional: quick search on load if ?q= is present
const params = new URLSearchParams(window.location.search);
if (params.get('q')){
  queryInput.value = params.get('q');
  form.dispatchEvent(new Event('submit'));
}
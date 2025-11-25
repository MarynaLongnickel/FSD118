async function postJSON(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  return r.json();
}

async function getJSON(url) {
  const r = await fetch(url, { credentials: 'include' });
  return r.json();
}

const loginForm = document.getElementById('loginForm');
if (loginForm) {
  loginForm.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const data = { username: form.username.value, password: form.password.value };
    const res = await postJSON('/api/login', data);
    if (res.success) window.location = '/dashboard';
    else document.getElementById('authMsg').innerText = res.error || 'Login failed';
  });
}
const registerForm = document.getElementById('registerForm');
if (registerForm) {
  registerForm.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const data = { username: form.username.value, password: form.password.value };
    const res = await postJSON('/api/register', data);
    if (res.success) {
      document.getElementById('authMsg').innerText = 'Account created — you can log in.';
      form.reset();
    } else document.getElementById('authMsg').innerText = res.error || 'Register failed';
  });
}

if (document.getElementById('searchInput')) {
  const searchInput = document.getElementById('searchInput');
  const searchResults = document.getElementById('searchResults');
  const watchlistEl = document.getElementById('watchlist');
  const btnLogout = document.getElementById('btnLogout');

  btnLogout.addEventListener('click', async () => {
    await postJSON('/api/logout', {});
    window.location = '/';
  });

  async function loadWatchlist() {
    const items = await getJSON('/api/watchlist');
    watchlistEl.innerHTML = '';
    items.forEach(it => {
      const li = document.createElement('li');
      li.textContent = `${it.symbol}${it.name ? ' — ' + it.name : ''}`;
      const del = document.createElement('button');
      del.textContent = 'Remove';
      del.style.marginLeft = '12px';
      del.onclick = async () => {
        await fetch(`/api/watchlist/${it.id}`, { method: 'DELETE', credentials: 'include' });
        loadWatchlist();
      };
      li.appendChild(del);
      watchlistEl.appendChild(li);
    });
  }

  searchInput.addEventListener('input', async (ev) => {
    const q = ev.target.value.trim();
    if (!q) { searchResults.innerHTML = ''; return }
    const results = await getJSON('/api/search?q=' + encodeURIComponent(q));
    searchResults.innerHTML = '';
    results.forEach(r => {
      const d = document.createElement('div');
      d.textContent = `${r.symbol}${r.name ? ' — ' + r.name : ''}`;
      const btn = document.createElement('button');
      btn.textContent = 'Add';
      btn.className = 'add-btn';
      btn.onclick = async () => {
        await postJSON('/api/watchlist', { symbol: r.symbol, name: r.name });
        loadWatchlist();
      };
      d.appendChild(btn);
      searchResults.appendChild(d);
    });
  });

  loadWatchlist();
}

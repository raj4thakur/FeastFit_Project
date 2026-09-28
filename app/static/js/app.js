/* FeastFit front-end: a thin layer over the JSON API (the backend is the star). */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const cap = (s) => String(s).replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  const TOKEN_KEY = 'ff_token';

  class ApiError extends Error {
    constructor(status, message, details) { super(message); this.status = status; this.details = details; }
  }

  async function api(path, { method = 'GET', body, form } = {}) {
    const headers = {};
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers.Authorization = `Bearer ${token}`;
    let payload;
    if (form) payload = form;
    else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
    const res = await fetch(path, { method, headers, body: payload });
    if (res.status === 204) return null;
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const err = data?.error || {};
      throw new ApiError(res.status, err.message || 'Something went wrong', err.details);
    }
    return data;
  }

  function toast(msg, type = '') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    $('#toasts').appendChild(el);
    setTimeout(() => el.remove(), 4500);
  }
  function showError(e) {
    const detail = Array.isArray(e.details) && e.details.length
      ? ' — ' + e.details.map((d) => `${d.field}: ${d.message}`).join('; ') : '';
    toast((e.message || 'Error') + detail, 'error');
  }

  let meta = null;
  const catLabels = {};
  async function getMeta() {
    if (!meta) {
      meta = await api('/api/meta');
      meta.categories.forEach((c) => { catLabels[c.value] = c.label; });
    }
    return meta;
  }
  const fillSelect = (sel, items, first) => {
    sel.innerHTML = (first ? `<option value="">${first}</option>` : '') +
      items.map((i) => `<option value="${esc(i.value ?? i)}">${esc(i.label ?? cap(i))}</option>`).join('');
  };

  /* ---------- auth / nav ---------- */
  let me = null;
  async function loadMe() {
    if (!localStorage.getItem(TOKEN_KEY)) return null;
    try { me = await api('/api/auth/me'); } catch { localStorage.removeItem(TOKEN_KEY); me = null; }
    return me;
  }
  function renderNav() {
    const nav = $('#nav-links');
    nav.innerHTML = me
      ? `<a href="/">Recipes</a><a href="/upload">Share a recipe</a><a href="/me">@${esc(me.username)}</a><a href="#" id="logout">Log out</a>`
      : `<a href="/">Recipes</a><a href="/login">Log in</a><a href="/register" class="btn btn-sm">Join free</a>`;
    const out = $('#logout');
    if (out) out.addEventListener('click', (e) => { e.preventDefault(); localStorage.removeItem(TOKEN_KEY); location.href = '/'; });
  }
  const requireLogin = () => { if (!me) { location.href = '/login'; return false; } return true; };

  /* ---------- shared card ---------- */
  const card = (r) => `
    <a class="card" href="/recipes/${encodeURIComponent(r.slug)}">
      <div class="card-img">${r.thumb_url ? `<img loading="lazy" src="${esc(r.thumb_url)}" alt="${esc(r.title)}">` : '<div class="ph">🍝</div>'}</div>
      <div class="card-body">
        <p class="eyebrow">${esc(cap(r.cuisine))} · ${esc(catLabels[r.category] || cap(r.category))}</p>
        <h3>${esc(r.title)}</h3>
        <p>${esc(r.description)}</p>
        <div class="tags">${r.diet_tags.slice(0, 3).map((t) => `<span class="tag">${esc(cap(t))}</span>`).join('')}</div>
        <div class="meta"><span>⏱ ${r.total_minutes} min</span><span>🔥 ${r.calories ?? '—'} kcal</span><span>★ ${r.avg_rating ?? 'New'}</span></div>
      </div>
    </a>`;

  /* ---------- pages ---------- */
  const pages = {};

  pages.home = async () => {
    const m = await getMeta();
    fillSelect($('#f-cuisine'), m.cuisines, 'All cuisines');
    fillSelect($('#f-diet'), m.diet_tags, 'Any diet');
    fillSelect($('#f-difficulty'), m.difficulties, 'Any difficulty');
    const chips = $('#chips');
    chips.innerHTML = `<button class="chip active" data-cat="">All</button>` +
      m.categories.slice(0, 6).map((c) => `<button class="chip" data-cat="${esc(c.value)}">${esc(c.label)}</button>`).join('');

    const state = { page: 1, category: '' };
    const grid = $('#grid');

    async function load() {
      const p = new URLSearchParams({ page: state.page, size: 9, sort: $('#f-sort').value });
      const add = (k, v) => { if (v) p.set(k, v); };
      add('q', $('#q').value.trim()); add('cuisine', $('#f-cuisine').value); add('diet', $('#f-diet').value);
      add('difficulty', $('#f-difficulty').value); add('max_minutes', $('#f-time').value); add('category', state.category);
      grid.innerHTML = '<div class="skeleton" style="height:340px"></div>'.repeat(3);
      try {
        const data = await api(`/api/recipes?${p}`);
        grid.innerHTML = data.items.length ? data.items.map(card).join('')
          : '<div class="empty"><h3>No recipes found</h3><p>Try different filters — or <a href="/upload">share your own</a>!</p></div>';
        $('#result-count').textContent = `${data.total} recipe${data.total === 1 ? '' : 's'}`;
        $('#pager').innerHTML = data.pages > 1
          ? `<button class="btn btn-ghost btn-sm" id="prev" ${state.page <= 1 ? 'disabled' : ''}>← Prev</button>
             <span class="muted">Page ${data.page} of ${data.pages}</span>
             <button class="btn btn-ghost btn-sm" id="next" ${state.page >= data.pages ? 'disabled' : ''}>Next →</button>` : '';
        $('#prev')?.addEventListener('click', () => { state.page--; load(); scrollTo({ top: 0, behavior: 'smooth' }); });
        $('#next')?.addEventListener('click', () => { state.page++; load(); scrollTo({ top: 0, behavior: 'smooth' }); });
      } catch (e) { showError(e); grid.innerHTML = ''; }
    }
    const reload = () => { state.page = 1; load(); };
    ['#f-cuisine', '#f-diet', '#f-difficulty', '#f-time', '#f-sort'].forEach((s) => $(s).addEventListener('change', reload));
    $('#hero-search').addEventListener('submit', (e) => { e.preventDefault(); reload(); });
    chips.addEventListener('click', (e) => {
      const b = e.target.closest('.chip'); if (!b) return;
      $$('.chip', chips).forEach((c) => c.classList.remove('active')); b.classList.add('active');
      state.category = b.dataset.cat; reload();
    });
    $('#f-reset').addEventListener('click', () => {
      ['#f-cuisine', '#f-diet', '#f-difficulty', '#f-time'].forEach((s) => { $(s).value = ''; });
      $('#f-sort').value = 'newest'; $('#q').value = ''; state.category = '';
      $$('.chip', chips).forEach((c, i) => c.classList.toggle('active', i === 0)); reload();
    });
    load();
  };

  pages.recipe = async () => {
    await getMeta();
    const root = $('#recipe-root');
    const slug = document.body.dataset.slug;
    let r;
    try { r = await api(`/api/recipes/slug/${encodeURIComponent(slug)}`); }
    catch (e) { root.innerHTML = `<div class="panel center"><h2>Recipe not found</h2><p class="muted">${esc(e.message)}</p><a class="btn" href="/">Browse recipes</a></div>`; return; }
    document.title = `${r.title} · FeastFit`;
    const owner = me && (me.id === r.author_id || me.is_admin);

    const stars = (n) => '★'.repeat(n) + '☆'.repeat(5 - n);
    const render = (reviews) => {
      root.innerHTML = `
      <div class="recipe-hero">
        ${r.image_url ? `<img src="${esc(r.image_url)}" alt="${esc(r.title)}">` : '<div class="ph-big">🍝</div>'}
        <div>
          <p class="eyebrow">${esc(cap(r.cuisine))} · ${esc(catLabels[r.category] || cap(r.category))}</p>
          <h1>${esc(r.title)}</h1>
          <p class="muted">by @${esc(r.author_name)} · <span class="stars">${r.avg_rating ? stars(Math.round(r.avg_rating)) : ''}</span> ${r.avg_rating ?? 'No ratings yet'} (${r.review_count})</p>
          <p>${esc(r.description)}</p>
          <div class="pills">
            <div class="pill"><b>${r.total_minutes} min</b>total</div>
            <div class="pill"><b>${r.servings}</b>servings</div>
            <div class="pill"><b>${esc(cap(r.difficulty))}</b>difficulty</div>
          </div>
          <div class="tags">${r.diet_tags.map((t) => `<span class="tag">${esc(cap(t))}</span>`).join('')}</div>
          ${r.calories != null || r.protein_g != null ? `<div class="nutri">
            <div><b>${r.calories ?? '—'}</b>kcal</div><div><b>${r.protein_g ?? '—'} g</b>protein</div>
            <div><b>${r.carbs_g ?? '—'} g</b>carbs</div><div><b>${r.fat_g ?? '—'} g</b>fat</div></div>
            <p class="small muted">Per serving</p>` : ''}
          <div class="actions">
            <button class="btn" id="fav-btn">${r.is_favorite ? '♥ Saved' : '♡ Save recipe'}</button>
            ${owner ? '<label class="btn btn-ghost">Change photo<input id="photo-input" type="file" accept="image/*" hidden></label><button class="btn btn-danger" id="del-btn">Delete</button>' : ''}
          </div>
        </div>
      </div>
      <div class="cols">
        <div class="panel"><h2>Ingredienti</h2><ul class="ing-list">
          ${r.ingredients.map((i) => `<li><span>${esc(i.quantity)}</span><span>${esc(i.name)}</span></li>`).join('')}</ul></div>
        <div class="panel"><h2>Preparazione</h2><ol class="steps">
          ${r.steps.map((s) => `<li>${esc(s.instruction)}</li>`).join('')}</ol></div>
      </div>
      <div class="panel" style="margin-top:2.5rem">
        <h2>Reviews</h2>
        ${me && me.id !== r.author_id ? `<form id="review-form" class="form" style="margin-bottom:1rem">
          <label>Your rating<select name="rating">${[5, 4, 3, 2, 1].map((n) => `<option value="${n}">${stars(n)}</option>`).join('')}</select></label>
          <label>Comment<textarea name="comment" rows="2" maxlength="2000"></textarea></label>
          <button class="btn btn-sm" type="submit" style="align-self:flex-start">Submit review</button></form>` : ''}
        ${reviews.length ? reviews.map((v) => `<div class="review"><span class="stars">${stars(v.rating)}</span> <b>@${esc(v.username)}</b>
          <p style="margin:.2rem 0 0">${esc(v.comment)}</p></div>`).join('') : '<p class="muted">No reviews yet.</p>'}
      </div>`;
      wire();
    };

    async function refresh() {
      r = await api(`/api/recipes/${r.id}`);
      render(await api(`/api/recipes/${r.id}/reviews`));
    }
    function wire() {
      $('#fav-btn').addEventListener('click', async () => {
        if (!requireLogin()) return;
        try {
          await api(`/api/recipes/${r.id}/favorite`, { method: r.is_favorite ? 'DELETE' : 'POST' });
          r.is_favorite = !r.is_favorite; $('#fav-btn').textContent = r.is_favorite ? '♥ Saved' : '♡ Save recipe';
        } catch (e) { showError(e); }
      });
      $('#del-btn')?.addEventListener('click', async () => {
        if (!confirm('Delete this recipe permanently?')) return;
        try { await api(`/api/recipes/${r.id}`, { method: 'DELETE' }); location.href = '/me'; } catch (e) { showError(e); }
      });
      $('#photo-input')?.addEventListener('change', async (e) => {
        const f = e.target.files[0]; if (!f) return;
        const fd = new FormData(); fd.append('file', f);
        try { await api(`/api/recipes/${r.id}/image`, { method: 'POST', form: fd }); toast('Photo updated', 'ok'); refresh(); } catch (err) { showError(err); }
      });
      $('#review-form')?.addEventListener('submit', async (e) => {
        e.preventDefault(); const fd = new FormData(e.target);
        try {
          await api(`/api/recipes/${r.id}/reviews`, { method: 'POST', body: { rating: +fd.get('rating'), comment: fd.get('comment') } });
          toast('Thanks for your review!', 'ok'); refresh();
        } catch (err) { showError(err); }
      });
    }
    render(await api(`/api/recipes/${r.id}/reviews`));
  };

  const bindForm = (id, handler) => {
    const form = $(id);
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = $('button[type=submit]', form); btn.disabled = true;
      try { await handler(new FormData(form)); } catch (err) { showError(err); } finally { btn.disabled = false; }
    });
  };
  async function login(username, password) {
    const data = await api('/api/auth/login', { method: 'POST', form: new URLSearchParams({ username, password }) });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    location.href = '/';
  }
  pages.login = () => bindForm('#login-form', (fd) => login(fd.get('username'), fd.get('password')));
  pages.register = () => bindForm('#register-form', async (fd) => {
    await api('/api/auth/register', { method: 'POST', body: { username: fd.get('username'), email: fd.get('email'), password: fd.get('password') } });
    await login(fd.get('username'), fd.get('password'));
  });

  pages.upload = async () => {
    if (!requireLogin()) return;
    const m = await getMeta();
    fillSelect($('#u-cuisine'), m.cuisines); $('#u-cuisine').value = 'italian';
    fillSelect($('#u-category'), m.categories); fillSelect($('#u-difficulty'), m.difficulties);
    $('#u-tags').innerHTML = m.diet_tags.map((t) => `<label><input type="checkbox" value="${esc(t)}">${esc(cap(t))}</label>`).join('');

    const addRow = (container, html) => {
      const div = document.createElement('div'); div.className = 'dyn-row'; div.innerHTML = html + '<button type="button" aria-label="Remove">×</button>';
      $('button', div).addEventListener('click', () => { if ($$('.dyn-row', container).length > 1) div.remove(); });
      container.appendChild(div);
    };
    const ing = $('#ing-rows'), steps = $('#step-rows');
    const addIng = () => addRow(ing, '<input placeholder="Ingredient, e.g. Spaghetti" class="i-name" maxlength="120"><input placeholder="Amount, e.g. 200 g" class="i-qty" maxlength="60">');
    const addStep = () => addRow(steps, '<input placeholder="Describe this step" class="s-text" maxlength="2000">');
    addIng(); addIng(); addStep(); addStep();
    $('#add-ing').addEventListener('click', addIng); $('#add-step').addEventListener('click', addStep);

    $('#photo').addEventListener('change', (e) => {
      const f = e.target.files[0], img = $('#photo-preview');
      if (f) { img.src = URL.createObjectURL(f); img.hidden = false; } else img.hidden = true;
    });

    bindForm('#recipe-form', async (fd) => {
      const num = (k) => (fd.get(k) === '' || fd.get(k) === null ? null : Number(fd.get(k)));
      const body = {
        title: fd.get('title'), description: fd.get('description'), cuisine: fd.get('cuisine'),
        category: fd.get('category'), difficulty: fd.get('difficulty'),
        diet_tags: $$('#u-tags input:checked').map((c) => c.value),
        prep_minutes: num('prep_minutes') ?? 0, cook_minutes: num('cook_minutes') ?? 0, servings: num('servings') ?? 2,
        calories: num('calories'), protein_g: num('protein_g'), carbs_g: num('carbs_g'), fat_g: num('fat_g'),
        ingredients: $$('.dyn-row', ing).map((r) => ({ name: $('.i-name', r).value.trim(), quantity: $('.i-qty', r).value.trim() })).filter((i) => i.name),
        steps: $$('.s-text', steps).map((s) => ({ instruction: s.value.trim() })).filter((s) => s.instruction),
      };
      const recipe = await api('/api/recipes', { method: 'POST', body });
      const file = $('#photo').files[0];
      if (file) {
        const up = new FormData(); up.append('file', file);
        try { await api(`/api/recipes/${recipe.id}/image`, { method: 'POST', form: up }); }
        catch (e) { toast('Recipe saved, but the photo failed: ' + e.message, 'error'); await new Promise((r) => setTimeout(r, 1800)); }
      }
      location.href = `/recipes/${encodeURIComponent(recipe.slug)}`;
    });
  };

  pages.profile = async () => {
    if (!requireLogin()) return;
    await getMeta();
    $('#p-name').textContent = `Ciao, ${me.username}`; $('#p-email').textContent = me.email;
    const grid = $('#p-grid');
    async function show(tab) {
      $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === tab));
      try {
        const items = await api(tab === 'mine' ? '/api/users/me/recipes' : '/api/users/me/favorites');
        grid.innerHTML = items.length ? items.map(card).join('')
          : `<div class="empty"><h3>${tab === 'mine' ? 'You haven\'t shared a recipe yet' : 'Nothing saved yet'}</h3>
             <p>${tab === 'mine' ? '<a href="/upload">Publish your first dish</a>' : '<a href="/">Browse recipes</a>'}</p></div>`;
      } catch (e) { showError(e); }
    }
    $$('.tab').forEach((t) => t.addEventListener('click', () => show(t.dataset.tab)));
    show('mine');
  };

  /* ---------- boot ---------- */
  (async () => {
    $('#year').textContent = new Date().getFullYear();
    await loadMe();
    renderNav();
    const page = document.body.dataset.page;
    if (pages[page]) pages[page]().catch(showError);
  })();
})();

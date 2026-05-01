const PILLARS = {
  cognitive_load: {
    label: 'Cognitive Load',
    icon:  '🧠',
    description: 'README clarity, run instructions, onboarding friction — can a coding agent get oriented without a guided tour?',
  },
  feedback: {
    label: 'Feedback Loops',
    icon:  '🔄',
    description: 'Test commands, CI configuration, lockfiles, evaluation harnesses — does the agent get a fast red/green signal on its changes?',
  },
  flow: {
    label: 'Flow & Reliability',
    icon:  '⚡',
    description: 'Entry points, automation, devcontainers, templates, contributor docs — once oriented, can the agent move without snags?',
  },
  safety: {
    label: 'Safety',
    icon:  '🛡️',
    description: 'Secrets hygiene, dependency-update automation, security policy, gitignore coverage — does the agent know the boundaries it must not cross?',
  },
};

// ── State ──────────────────────────────────────────────────────────────────
//   curatedRepos    — from data/scores.json            (the canonical leaderboard)
//   experimentRepos — from data/scores_experiment.json (daily-discovered pool; may be empty / absent)
//   scope           — which slice the user is viewing: 'curated' | 'experiment' | 'combined'
let curatedRepos    = [];
let experimentRepos = [];
let curatedMeta     = { last_updated: null, total: 0 };
let experimentMeta  = { last_updated: null, total: 0, available: false };
let scope     = 'curated';
let allRepos  = [];     // recomputed by setScope()
let page      = 1;
let pageSize  = 20;
let sortKey   = 'score';
let sortDir   = -1;   // -1 = descending (high→low), 1 = ascending (low→high)

function recomputeAllRepos() {
  if (scope === 'curated') {
    allRepos = curatedRepos;
  } else if (scope === 'experiment') {
    allRepos = experimentRepos;
  } else {
    // combined: dedupe by full_name (curated wins on collision)
    const seen = new Map();
    for (const r of curatedRepos) seen.set((r.repo || '').toLowerCase(), { ...r, _scope: 'curated' });
    for (const r of experimentRepos) {
      const k = (r.repo || '').toLowerCase();
      if (!seen.has(k)) seen.set(k, { ...r, _scope: 'experiment' });
    }
    allRepos = [...seen.values()];
  }
}

function setScope(next) {
  if (next === scope) return;
  if (next === 'experiment' && !experimentMeta.available) return;
  if (next === 'combined'   && !experimentMeta.available) return;
  scope = next;
  page  = 1;
  recomputeAllRepos();
  document.getElementById('sRepos').textContent = allRepos.length;
  renderPage();
}

// ── Sort & page helpers ────────────────────────────────────────────────────
function getSorted() {
  return [...allRepos].sort((a, b) => {
    let cmp = 0;
    if      (sortKey === 'score') cmp = a.overall_score - b.overall_score;
    else if (sortKey === 'stars') cmp = a.stars - b.stars;
    else if (sortKey === 'name')  cmp = a.repo.localeCompare(b.repo);
    return sortDir * -cmp;
  });
}

function totalPages() { return Math.max(1, Math.ceil(allRepos.length / pageSize)); }

function getPageRepos() {
  const sorted = getSorted();
  const start  = (page - 1) * pageSize;
  return sorted.slice(start, start + pageSize);
}

function setSort(key) {
  if (sortKey === key) {
    sortDir *= -1;
  } else {
    sortKey = key;
    sortDir = key === 'name' ? 1 : -1;
  }
  page = 1;
  renderPage();
}

function setPageSize(n) {
  pageSize = n;
  page = 1;
  renderPage();
}

function goPage(p) {
  const total = totalPages();
  if (p < 1 || p > total) return;
  page = p;
  renderPage();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Utilities ──────────────────────────────────────────────────────────────
function scoreColor(pct) {
  if (pct >= 80) return 'var(--accent)';
  if (pct >= 65) return 'var(--green)';
  if (pct >= 50) return 'var(--blue)';
  if (pct >= 35) return 'var(--yellow)';
  if (pct >= 20) return 'var(--orange)';
  return 'var(--red)';
}

function ring(pct, size = 52) {
  const r    = size * 0.42;
  const cx   = size / 2;
  const circ = +(2 * Math.PI * r).toFixed(2);
  const off  = +(circ * (1 - pct / 100)).toFixed(2);
  const col  = scoreColor(pct);
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="var(--surface2)" stroke-width="4"/>
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${col}" stroke-width="4"
      stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${off}"
      style="transition:stroke-dashoffset 1s ease"/>
  </svg>`;
}

function starsFmt(n) {
  if (n >= 1000) return (n / 1000).toFixed(0) + 'k';
  return n;
}

function timeAgo(iso) {
  const d  = Date.now() - new Date(iso).getTime();
  const m  = Math.floor(d / 60000);
  const h  = Math.floor(m / 60);
  const dy = Math.floor(h / 24);
  if (dy > 0) return dy + 'd ago';
  if (h  > 0) return h  + 'h ago';
  if (m  > 0) return m  + 'm ago';
  return 'just now';
}

function nextScan() {
  const now  = new Date();
  const next = new Date(now);
  next.setUTCHours(6, 0, 0, 0);
  if (next <= now) next.setUTCDate(next.getUTCDate() + 1);
  const diff = next - now;
  return `${Math.floor(diff / 3600000)}h ${Math.floor((diff % 3600000) / 60000)}m`;
}

function rankLabel(n) {
  if (n === 1) return '<span class="rank rank-medal">🥇</span>';
  if (n === 2) return '<span class="rank rank-medal">🥈</span>';
  if (n === 3) return '<span class="rank rank-medal">🥉</span>';
  return `<span class="rank">#${n}</span>`;
}

// ── Toolbar HTML ───────────────────────────────────────────────────────────
function renderToolbar() {
  const arrow  = sortDir === -1 ? '↓' : '↑';
  const mkBtn  = (key, label) => {
    const active = sortKey === key;
    return `<button class="sort-btn${active ? ' active' : ''}" onclick="setSort('${key}')">
      ${label}${active ? ` <span class="sort-arrow">${arrow}</span>` : ''}
    </button>`;
  };
  const expDisabled = experimentMeta.available ? '' : 'disabled title="No experiment pool yet"';
  const mkScope = (key, label, count) => {
    const active = scope === key;
    const disabled = (key !== 'curated' && !experimentMeta.available) ? 'disabled' : '';
    return `<button class="scope-btn${active ? ' active' : ''}" ${disabled}
      onclick="setScope('${key}')" title="${label}">${label}${count != null ? ` (${count})` : ''}</button>`;
  };
  const pageSizes = [10, 20, 25, 50].map(n =>
    `<option value="${n}"${n === pageSize ? ' selected' : ''}>${n}</option>`).join('');
  const start = (page - 1) * pageSize + 1;
  const end   = Math.min(page * pageSize, allRepos.length);
  const combinedCount = experimentMeta.available
    ? new Set([
        ...curatedRepos.map(r => (r.repo || '').toLowerCase()),
        ...experimentRepos.map(r => (r.repo || '').toLowerCase()),
      ]).size
    : null;

  return `
    <div class="toolbar">
      <div class="sort-group">
        <span class="sort-label">Scope</span>
        <div class="scope-group">
          ${mkScope('curated',    'Curated',    curatedMeta.total)}
          ${mkScope('experiment', 'Experiment', experimentMeta.available ? experimentMeta.total : null)}
          ${mkScope('combined',   'Combined',   combinedCount)}
        </div>
      </div>
      <div class="sort-group">
        <span class="sort-label">Sort by</span>
        ${mkBtn('score', 'Score')}
        ${mkBtn('stars', 'Stars')}
        ${mkBtn('name',  'Name')}
      </div>
      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <span class="result-count">${start}–${end} of ${allRepos.length}</span>
        <div class="page-size-wrap">
          <label class="page-size-label" for="pageSel">Per page</label>
          <select class="page-size-sel" id="pageSel" onchange="setPageSize(+this.value)">
            ${pageSizes}
          </select>
        </div>
      </div>
    </div>`;
}

// ── Pagination HTML ────────────────────────────────────────────────────────
function pageRange(cur, total) {
  if (total <= 9) return Array.from({ length: total }, (_, i) => i + 1);
  const set = new Set([1, 2, cur - 1, cur, cur + 1, total - 1, total]
    .filter(p => p >= 1 && p <= total));
  const arr = [...set].sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i < arr.length; i++) {
    if (i > 0 && arr[i] - arr[i - 1] > 1) out.push('…');
    out.push(arr[i]);
  }
  return out;
}

function renderPagination() {
  const total = totalPages();
  if (total <= 1) return '';
  const range = pageRange(page, total);
  const pages = range.map(p =>
    p === '…'
      ? `<span class="page-ellipsis">…</span>`
      : `<button class="page-btn${p === page ? ' active' : ''}" onclick="goPage(${p})">${p}</button>`
  ).join('');
  return `
    <div class="pagination">
      <button class="page-btn" onclick="goPage(${page - 1})" ${page === 1 ? 'disabled' : ''}>← Prev</button>
      ${pages}
      <button class="page-btn" onclick="goPage(${page + 1})" ${page === total ? 'disabled' : ''}>Next →</button>
    </div>`;
}

// ── Card HTML ──────────────────────────────────────────────────────────────
function buildCard(repo, idx) {
  const delay  = Math.min(idx * 0.04, 0.3).toFixed(2);
  const pct    = repo.overall_score;
  const col    = scoreColor(pct);
  const topics = (repo.topics || []).slice(0, 3).map(t => `<span>#${t}</span>`).join('');

  const pillarBars = Object.entries(PILLARS).map(([key, meta]) => {
    const score = (repo.pillars || {})[key];
    if (score == null) return '';
    const bp = score.toFixed(1);
    return `
      <div class="cat-row">
        <div class="cat-label" title="${meta.description}">${meta.icon} ${meta.label}</div>
        <div class="bar-track"><div class="bar-fill" data-pct="${bp}"></div></div>
        <div class="cat-score">${bp}/100</div>
      </div>`;
  }).join('');

  const findings = (repo.top_findings || []);
  const findingsHtml = findings.length === 0 ? '' : `
    <div class="findings-section">
      <div class="findings-title">Top Findings</div>
      ${findings.map(f => `
        <div class="finding-item">
          <span class="finding-badge badge-${f.severity}">${f.severity}</span>
          <div class="finding-body">
            <div class="finding-msg">${f.message}</div>
            ${f.fix_hint ? `<div class="finding-hint">💡 ${f.fix_hint}</div>` : ''}
          </div>
        </div>`).join('')}
    </div>`;

  return `
    <div class="repo-card" style="animation-delay:${delay}s">
      <div class="card-header" onclick="toggleCard(this.parentElement)">
        ${rankLabel(repo.rank)}
        <div class="avatar">
          <img src="${repo.avatar}" alt="${repo.owner}" loading="lazy" onerror="this.style.display='none'"/>
        </div>
        <div class="repo-info">
          <div class="repo-name">
            <a href="${repo.url}" target="_blank" rel="noopener"
               onclick="event.stopPropagation()">${repo.owner}/${repo.name}</a>
            ${repo._scope === 'experiment' ? '<span class="scope-tag" title="Discovered automatically; not in the curated list">Experiment</span>' : ''}
          </div>
          <div class="repo-meta">
            ${repo.language ? `<span>◉ ${repo.language}</span>` : ''}
            <span>★ ${starsFmt(repo.stars)}</span>
            ${topics}
          </div>
        </div>
        <div class="score-section">
          <div class="grade grade-${repo.grade}">${repo.grade}</div>
          <div class="ring-wrap">
            ${ring(pct)}
            <div class="ring-label" style="color:${col}">${pct}</div>
          </div>
          <span class="chevron">▾</span>
        </div>
      </div>
      <div class="breakdown">
        ${repo.description ? `<div class="desc">${repo.description}</div>` : ''}
        ${pillarBars}
        ${findingsHtml}
      </div>
    </div>`;
}

function toggleCard(card) {
  const opening = !card.classList.contains('open');
  card.classList.toggle('open', opening);
  card.querySelectorAll('.bar-fill').forEach(bar => {
    bar.style.width = opening ? bar.dataset.pct + '%' : '0';
  });
}

// ── Main render ────────────────────────────────────────────────────────────
function renderPage() {
  document.getElementById('toolbar').innerHTML    = renderToolbar();
  document.getElementById('leaderboard').innerHTML = getPageRepos()
    .map((r, i) => buildCard(r, i)).join('') || '<div class="state">No data yet.</div>';
  document.getElementById('pagination').innerHTML = renderPagination();
}

// ── Data loading ───────────────────────────────────────────────────────────
//   The page reads two sibling files:
//     data/scores.json              — curated leaderboard (always present)
//     data/scores_experiment.json   — daily-discovered pool (may be missing /
//                                     empty; the page degrades to curated-only)
async function fetchJson(path) {
  const res = await fetch(path + '?_=' + Date.now(), { cache: 'no-store' });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  return res.json();
}

async function load() {
  let curatedErr = null;
  try {
    const data = await fetchJson('./data/scores.json');
    curatedRepos       = data.repos || [];
    curatedMeta        = { last_updated: data.last_updated, total: data.total_repos || curatedRepos.length };
    document.getElementById('sUpdated').textContent = timeAgo(data.last_updated);
  } catch (e) {
    curatedErr = e;
  }

  try {
    const data = await fetchJson('./data/scores_experiment.json');
    const repos = data.repos || [];
    if (repos.length > 0) {
      experimentRepos = repos;
      experimentMeta  = {
        last_updated: data.last_updated,
        total: data.total_repos || repos.length,
        available: true,
      };
    } else {
      experimentMeta = { last_updated: null, total: 0, available: false };
    }
  } catch {
    // Missing experiment file is expected in older deployments — silent.
    experimentMeta = { last_updated: null, total: 0, available: false };
  }

  document.getElementById('sNext').textContent = nextScan();

  if (curatedErr && experimentRepos.length === 0) {
    document.getElementById('leaderboard').innerHTML =
      `<div class="state">⚠️ Could not load scores.<br>
       <small style="color:var(--faint)">${curatedErr.message}</small></div>`;
    return;
  }

  // If curated failed but experiment loaded, switch the user there automatically.
  if (curatedErr && experimentRepos.length > 0) {
    scope = 'experiment';
  }

  recomputeAllRepos();
  document.getElementById('sRepos').textContent = allRepos.length;
  renderPage();
}

// ── Init ───────────────────────────────────────────────────────────────────
load();
setInterval(load, 5 * 60 * 1000);
setInterval(() => {
  const el = document.getElementById('sNext');
  if (el) el.textContent = nextScan();
}, 60 * 1000);

document.getElementById('toggleMethod').addEventListener('click', e => {
  e.preventDefault();
  const p = document.getElementById('methodPanel');
  p.style.display = p.style.display === 'none' ? 'block' : 'none';
});

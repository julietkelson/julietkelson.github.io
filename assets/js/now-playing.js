(function () {
  const ROOT_SEL = '[data-np]';
  const POLL_MS = 60_000;
  const FEATURE_KEYS = [
    'energy', 'danceability', 'valence',
    'acousticness', 'instrumentalness'
  ];
  const FEATURE_LABELS = {
    energy: 'ENERGY',
    danceability: 'UPBEAT',
    valence: 'VALENCE',
    acousticness: 'ACOUSTIC',
    instrumentalness: 'INSTRUMENTAL',
  };

  let pollTimer = null;
  let lastGeneratedAt = null;

  function fmt(n) {
    return (Math.round(n * 100) / 100).toFixed(2);
  }

  function shortDate(iso) {
    const [, m, d] = iso.split('-');
    return `${parseInt(m, 10)}/${parseInt(d, 10)}`;
  }

  function renderTrend(container, series) {
    if (!container) return;
    const pts = Array.isArray(series) ? series : [];
    if (pts.length < 2) {
      container.innerHTML = '';
      container.hidden = true;
      return;
    }
    container.hidden = false;

    const W = 100, H = 64;
    const n = pts.length;
    const x = (i) => (i / (n - 1)) * W;
    const y = (v) => (1 - Math.max(0, Math.min(1, v))) * H;
    const path = (key) =>
      pts.map((d, i) => `${x(i).toFixed(2)},${y(d[key]).toFixed(2)}`).join(' ');

    container.innerHTML = `
      <div class="np__trend-legend">
        <span class="np__trend-key np__trend-key--energy">ENERGY</span>
        <span class="np__trend-key np__trend-key--valence">VALENCE</span>
      </div>
      <div class="np__trend-chart">
        <div class="np__trend-yaxis" aria-hidden="true">
          <span>1</span><span>0.5</span><span>0</span>
        </div>
        <div class="np__trend-plot" data-np-plot>
          <svg class="np__trend-svg" viewBox="0 0 ${W} ${H}"
               preserveAspectRatio="none" aria-hidden="true">
            <polyline class="np__trend-line np__trend-line--valence"
                      vector-effect="non-scaling-stroke" points="${path('valence')}" />
            <polyline class="np__trend-line np__trend-line--energy"
                      vector-effect="non-scaling-stroke" points="${path('energy')}" />
          </svg>
          <div class="np__trend-midline" aria-hidden="true"></div>
        </div>
      </div>
      <div class="np__trend-dates">
        <span>${shortDate(pts[0].date)}</span>
        <span>${shortDate(pts[n - 1].date)}</span>
      </div>
    `;
  }

  function render(root, data) {
    root.hidden = false;
    const bars = root.querySelector('[data-np-bars]');
    const genres = root.querySelector('[data-np-genres]');
    const meta = root.querySelector('[data-np-meta]');
    const trend = root.querySelector('[data-np-trend]');

    if (data && data.state === 'calibrating') {
      root.classList.add('np--calibrating');
      bars.innerHTML = '';
      genres.textContent = '';
      meta.textContent = '';
      if (trend) { trend.innerHTML = ''; trend.hidden = true; }
      lastGeneratedAt = data.generated_at || null;
      return;
    }

    if (data.generated_at && data.generated_at === lastGeneratedAt) return;
    lastGeneratedAt = data.generated_at;

    root.classList.remove('np--calibrating');

    const artists = data.totals && data.totals.unique_artists;
    const bpm = data.tempo_mean_bpm;

    const targets = FEATURE_KEYS.map((key) => {
      const value = data.audio_features_mean[key];
      const pct = Math.max(0, Math.min(1, value)) * 100;
      return { key, value, pct };
    });

    bars.innerHTML = targets.map((t) => `
      <div class="np__bar-label">${FEATURE_LABELS[t.key]}</div>
      <div class="np__bar-track"><div class="np__bar-fill" data-target="${t.pct.toFixed(1)}" style="width:0%"></div></div>
      <div class="np__bar-value">${fmt(t.value)}</div>
    `).join('');

    const g = (data.top_genres || []).map(x => x.name).join(' · ');
    genres.textContent = g;

    meta.textContent = `${artists} artists · ${Math.round(bpm)} bpm avg`;

    renderTrend(trend, data.daily_series);

    requestAnimationFrame(() => {
      bars.querySelectorAll('.np__bar-fill').forEach((el, idx) => {
        setTimeout(() => {
          el.style.width = el.dataset.target + '%';
        }, idx * 90);
      });
    });
  }

  async function fetchOnce(root) {
    try {
      const resp = await fetch(`/data/aggregates.json?t=${Date.now()}`, {
        cache: 'no-store',
      });
      if (!resp.ok) return;
      const data = await resp.json();
      render(root, data);
    } catch (_e) {
      // Silent fail — leave the last rendered state up.
    }
  }

  function startPolling(root) {
    if (pollTimer) return;
    pollTimer = setInterval(() => {
      if (!document.hidden) fetchOnce(root);
    }, POLL_MS);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const root = document.querySelector(ROOT_SEL);
    if (!root) return;
    fetchOnce(root);
    startPolling(root);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stopPolling();
      else { fetchOnce(root); startPolling(root); }
    });
  });
})();

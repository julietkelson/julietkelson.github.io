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

  function render(root, data) {
    root.hidden = false;
    const bars = root.querySelector('[data-np-bars]');
    const genres = root.querySelector('[data-np-genres]');
    const meta = root.querySelector('[data-np-meta]');

    if (data && data.state === 'calibrating') {
      root.classList.add('np--calibrating');
      bars.innerHTML = '';
      genres.textContent = '';
      meta.textContent = '';
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

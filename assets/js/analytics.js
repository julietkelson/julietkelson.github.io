(function () {
  function sendEvent(params) {
    if (typeof gtag === 'function') {
      gtag('event', 'click', params);
    } else {
      // gtag not yet loaded — queue via dataLayer directly
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ event: 'click', ...params });
    }
  }

  // Design system block prefixes — maps DOM hierarchy to click_location values
  var LOCATION_PREFIXES = [
    'fn-nav', 'fn-footer',
    'home-hero', 'home-entry', 'home-work',
    'work-feature', 'work-described', 'work-impact',
    'cv-hero', 'cv-sidebar', 'cv-role', 'cv-chapter',
    'writing-feature', 'writing-hero', 'writing-posts',
    'about-hero', 'about-portrait',
    'covid-hero', 'covid-posts',
    'post-hero', 'post-body', 'essay-pager',
    'music-hero', 'music-'
  ];

  var SOCIAL_DOMAINS = ['linkedin.com', 'github.com', 'spotify.com'];

  // Walk up the DOM to find the nearest design-system block class
  function inferLocation(el) {
    var node = el.parentElement;
    while (node && node !== document.body) {
      var classes = Array.from(node.classList);
      for (var i = 0; i < classes.length; i++) {
        var cls = classes[i];
        for (var j = 0; j < LOCATION_PREFIXES.length; j++) {
          if (cls.indexOf(LOCATION_PREFIXES[j]) === 0) {
            return cls.split('__')[0];
          }
        }
      }
      node = node.parentElement;
    }
    return 'page';
  }

  function inferType(el) {
    // Explicit data attribute always wins
    if (el.dataset.trackType) return el.dataset.trackType;

    var location = inferLocation(el);

    // Nav links
    if (location === 'fn-nav') return 'nav';

    // External links
    var isExternal = el.target === '_blank' || (el.hostname && el.hostname !== window.location.hostname);
    if (isExternal) {
      return SOCIAL_DOMAINS.some(function (d) { return el.href.indexOf(d) !== -1; })
        ? 'social'
        : 'external';
    }

    // Internal styled CTAs (classes ending in __link, __contact-link, __download, __cta)
    if (el.className && el.className.match(/__link|__contact.link|__download|__cta/)) return 'cta';

    // Internal navigation
    return 'internal';
  }

  function cleanText(el) {
    // Pull from data attribute or element text; strip arrow characters
    var text = el.dataset.trackText || el.textContent || '';
    return text.trim().replace(/\s+/g, ' ').replace(/[←-↙⇠-⇿]/g, '').trim();
  }

  // Sanitize URL — strip mailto: addresses and any query params that could carry PII
  function safeUrl(el) {
    var href = el.getAttribute('href') || '';
    if (href.indexOf('mailto:') === 0) return 'mailto:';
    try {
      var u = new URL(el.href);
      u.search = '';   // strip query string
      u.hash = '';
      return u.toString();
    } catch (e) {
      return href.split('?')[0];
    }
  }

  function trackLinks() {
    document.querySelectorAll('a[href]:not([data-no-track])').forEach(function (el) {
      // Skip fragment-only or javascript: links
      if (!el.href || el.href.indexOf('javascript:') === 0) return;

      el.addEventListener('click', function () {
        gtag('event', 'click', {
          click_text:     cleanText(el),
          click_type:     inferType(el),
          click_location: el.dataset.trackLocation || inferLocation(el),
          click_url:      safeUrl(el)
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', trackLinks);
  } else {
    trackLinks();
  }
})();

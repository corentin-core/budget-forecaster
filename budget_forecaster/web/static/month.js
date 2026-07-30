// Swipe left/right on the Month view to move to the next/previous month.
(function () {
  'use strict';
  var nav = document.querySelector('.month-nav[data-prev-url]');
  if (!nav) return;

  var startX = 0;
  var startY = 0;
  document.addEventListener(
    'touchstart',
    function (e) {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
    },
    { passive: true },
  );
  document.addEventListener(
    'touchend',
    function (e) {
      var dx = e.changedTouches[0].clientX - startX;
      var dy = e.changedTouches[0].clientY - startY;
      // Only a clearly horizontal swipe navigates (don't hijack scrolling).
      if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      var url = nav.getAttribute(dx < 0 ? 'data-next-url' : 'data-prev-url');
      if (url) window.location.href = url;
    },
    { passive: true },
  );
})();

// Expand/collapse a category drill-down under its month row. The open category
// is mirrored into the URL (?open=<cat>) so the back button and the "return to"
// links from edit/detail pages land back on the same expanded row.
(function () {
  'use strict';

  function collapse(btn) {
    var row = document.getElementById(btn.dataset.target);
    if (row) row.hidden = true;
    btn.setAttribute('aria-expanded', 'false');
  }

  function expand(btn, focus) {
    var row = document.getElementById(btn.dataset.target);
    if (!row) return;
    var slot = row.querySelector('.detail-slot');
    // Show first so the row appears even if the fragment load is slow; reload
    // each time so edits made and returned-from show fresh data.
    row.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
    window.htmx.ajax('GET', btn.dataset.url, { target: slot, swap: 'innerHTML' });
    if (focus) slot.focus();
  }

  function syncUrl(cat) {
    var url = location.pathname + (cat ? '?open=' + encodeURIComponent(cat) : '');
    window.history.replaceState(null, '', url);
  }

  function toggle(btn) {
    if (btn.getAttribute('aria-expanded') === 'true') {
      collapse(btn);
      syncUrl(null);
    } else {
      expand(btn, true);
      syncUrl(btn.dataset.cat);
    }
  }

  document.querySelectorAll('.cat-toggle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      toggle(btn);
    });
  });

  // The row highlights as one, so the figures open the drill-down too — the
  // category name is where the keyboard and a no-JS reader reach it.
  document.addEventListener('click', function (event) {
    if (event.target.closest('a, button, select, input, label, summary')) return;
    var row = event.target.closest('.review tr.row-hover');
    var btn = row && row.querySelector('.cat-toggle');
    if (btn) toggle(btn);
  });

  // Re-open the category carried in the URL (a previous expand, or a "return to"
  // link from an edit/detail page). Deferred to load so htmx.ajax is ready.
  function reopenFromUrl() {
    var open = new URLSearchParams(location.search).get('open');
    if (!open) return;
    var target = document.querySelector('.cat-toggle[data-cat="' + open + '"]');
    if (target && target.getAttribute('aria-expanded') !== 'true') {
      expand(target, false);
      target.scrollIntoView({ block: 'center' });
    }
  }

  if (document.readyState === 'complete') {
    reopenFromUrl();
  } else {
    window.addEventListener('load', reopenFromUrl);
  }
})();

// Tooltips for [data-tip] elements: hover on desktop, tap on mobile.
(function () {
  'use strict';

  function init() {
    var bubble = document.createElement('div');
    bubble.className = 'tip-bubble';
    bubble.hidden = true;
    document.body.appendChild(bubble);
    var current = null;

    function show(el) {
      bubble.textContent = el.getAttribute('data-tip');
      bubble.hidden = false;
      var rect = el.getBoundingClientRect();
      var top = rect.top + window.scrollY - bubble.offsetHeight - 8;
      if (top < window.scrollY) {
        top = rect.bottom + window.scrollY + 8; // flip below if no room above
      }
      var left = rect.left + window.scrollX + rect.width / 2 - bubble.offsetWidth / 2;
      left = Math.max(8, Math.min(window.innerWidth - bubble.offsetWidth - 8, left));
      bubble.style.top = top + 'px';
      bubble.style.left = left + 'px';
      current = el;
    }

    function hide() {
      bubble.hidden = true;
      current = null;
    }

    document.querySelectorAll('[data-tip]').forEach(function (el) {
      el.addEventListener('mouseenter', function () {
        show(el);
      });
      el.addEventListener('mouseleave', hide);
      el.addEventListener('focus', function () {
        show(el);
      });
      el.addEventListener('blur', hide);
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        if (current === el) {
          hide();
        } else {
          show(el);
        }
      });
    });

    // A tap/click anywhere else dismisses the bubble.
    document.addEventListener('click', function () {
      if (current) hide();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

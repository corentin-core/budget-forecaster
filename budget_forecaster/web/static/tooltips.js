// Tooltips for [data-tip] elements: hover on desktop, tap on mobile.
//
// Delegated, because htmx swaps bring new elements in, and because a listener on
// the element had to stop propagation to survive the dismiss-on-outside-click —
// which swallowed the click of the row the tip sat in.
(function () {
  'use strict';

  // A tap emits mouseover before click, so on a touch screen the hover path
  // opens the tip and the click that follows closes it in the same gesture.
  var hoverable = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  function init() {
    var bubble = document.createElement('div');
    bubble.className = 'tip-bubble';
    bubble.hidden = true;
    document.body.appendChild(bubble);
    var current = null;
    var shownBy = null;

    function show(el, how) {
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
      shownBy = how;
    }

    function hide() {
      bubble.hidden = true;
      current = null;
      shownBy = null;
    }

    // One handler decides: the tip toggles, anything else dismisses. The event
    // keeps bubbling either way, so the row underneath still navigates.
    //
    // A click only closes what a previous click opened. One tap is a whole
    // sequence — focus, then a synthetic hover on a hybrid screen, then the
    // click — and any of those showing the tip would have the click close it
    // again before it could be read.
    document.addEventListener('click', function (event) {
      var el = event.target.closest('[data-tip]');
      if (!el) {
        if (current) hide();
      } else if (current === el && shownBy === 'click') {
        hide();
      } else {
        show(el, 'click');
      }
    });

    // Leaving the element closes what hovering opened. A clicked tip stays: the
    // pointer has to travel to reach a long bubble, and the click that opened it
    // was a deliberate ask.
    if (hoverable) {
      document.addEventListener('mouseover', function (event) {
        var el = event.target.closest('[data-tip]');
        if (el) {
          if (current !== el) show(el, 'hover');
        } else if (current && shownBy === 'hover') {
          hide();
        }
      });
    }

    // focusin/focusout, because focus and blur do not bubble. Only a keyboard
    // focus shows the tip: a pointer focus is part of the click above.
    document.addEventListener('focusin', function (event) {
      var el = event.target.closest('[data-tip]');
      if (el && el.matches(':focus-visible')) show(el, 'focus');
    });
    // Only the tipped element losing focus counts. An htmx swap that replaces a
    // focused control elsewhere blurs it too, and that must not take the bubble.
    document.addEventListener('focusout', function (event) {
      if (event.target === current) hide();
    });

    // An out-of-band swap detaches the element the bubble points at, leaving it
    // floating over content it no longer describes.
    document.body.addEventListener('htmx:afterSwap', function () {
      if (current && !current.isConnected) hide();
    });

    // The position was clamped against the old viewport width.
    window.addEventListener('resize', function () {
      if (current) hide();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

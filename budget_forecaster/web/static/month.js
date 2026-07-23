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

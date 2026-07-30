// Theme switcher: Auto / Light / Dark, stored per device.
//
// Applying a theme writes color-scheme on the root element; the tokens are
// light-dark() pairs, so the palette follows. An inline head script reads the
// same key, early enough that the first paint is already the right theme.
(function () {
  'use strict';

  var KEY = 'theme';

  function stored() {
    try {
      var mode = localStorage.getItem(KEY);
      return mode === 'light' || mode === 'dark' ? mode : 'auto';
    } catch (e) {
      return 'auto';
    }
  }

  function apply(mode) {
    // Empty gives the decision back to the stylesheet's `light dark`: the device.
    document.documentElement.style.colorScheme = mode === 'auto' ? '' : mode;
    try {
      if (mode === 'auto') {
        localStorage.removeItem(KEY);
      } else {
        localStorage.setItem(KEY, mode);
      }
    } catch (e) {
      /* Storage denied: the choice holds for this page only. */
    }
  }

  function init() {
    var group = document.querySelector('[data-theme-switch]');
    if (!group) return;
    var buttons = group.querySelectorAll('button[data-theme]');

    function mark(mode) {
      buttons.forEach(function (button) {
        var on = button.dataset.theme === mode;
        button.classList.toggle('active', on);
        button.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }

    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        apply(button.dataset.theme);
        mark(button.dataset.theme);
      });
    });

    // The mode lives in storage, so which button is on is not something the
    // server can render.
    mark(stored());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

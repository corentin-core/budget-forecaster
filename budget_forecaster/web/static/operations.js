// Ledger selection mode. Checking any row shows the bulk bar and takes the
// inline category selects out of play, so categorization goes through one path
// at a time (bulk bar) — never a per-row select and a multi-select at once.
(function () {
  'use strict';

  var bar = document.getElementById('bulk-bar');
  if (!bar) return;
  var countEl = bar.querySelector('[data-bulk-count]');
  var categoryEl = bar.querySelector('#bulk-category');
  var applyEl = bar.querySelector('[data-bulk-apply]');

  function selected() {
    return document.querySelectorAll('.row-select:checked');
  }

  // The page reserves what the fixed bar covers, or the last rows are
  // unreachable while choosing. Measured: the labels wrap onto 1 or 2 lines.
  function reserve() {
    var height = bar.hidden ? 0 : bar.offsetHeight;
    document.documentElement.style.setProperty('--bulk-h', height + 'px');
  }

  function sync() {
    var n = selected().length;
    countEl.textContent = n;
    bar.hidden = n === 0;
    document.querySelectorAll('.row-category').forEach(function (sel) {
      sel.disabled = n > 0;
    });
    reserve();
  }

  window.addEventListener('resize', reserve);

  document.addEventListener('change', function (e) {
    if (e.target.classList.contains('row-select')) sync();
  });

  categoryEl.addEventListener('change', function () {
    applyEl.disabled = !categoryEl.value;
  });

  bar.querySelector('[data-bulk-clear]').addEventListener('click', function () {
    selected().forEach(function (cb) {
      cb.checked = false;
    });
    sync();
  });

  // Rows are replaced on filter change / bulk categorize; selection resets.
  document.body.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail.target && e.detail.target.id === 'ledger-area') sync();
  });

  sync();
})();

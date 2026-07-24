// Ledger selection mode. Checking any row shows the bulk bar and makes the
// inline category selects inert, so categorization goes through one path at a
// time (bulk bar) — never a per-row select and a multi-select at once.
(function () {
  'use strict';

  var bar = document.getElementById('bulk-bar');
  if (!bar) return;
  var countEl = bar.querySelector('[data-bulk-count]');

  function selected() {
    return document.querySelectorAll('.row-select:checked');
  }

  function sync() {
    var n = selected().length;
    countEl.textContent = n;
    bar.hidden = n === 0;
    document.querySelectorAll('.row-category').forEach(function (sel) {
      sel.disabled = n > 0;
    });
  }

  document.addEventListener('change', function (e) {
    if (e.target.classList.contains('row-select')) sync();
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

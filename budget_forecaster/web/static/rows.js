// A highlighted row is a click target: anywhere on it goes where its `data-href`
// says. The inner link stays for the keyboard and for no-JS.
//
// Delegated, because rows arrive from htmx swaps: the ledger replaces a row on
// every categorization, and the month drill-down is a fragment.
(function () {
  'use strict';

  // Anything with an action of its own wins: a chip going elsewhere, the
  // category select, a selection checkbox, the link icon.
  var OWN_ACTION = 'a, button, select, input, label, summary, textarea';

  document.addEventListener('click', function (event) {
    var row = event.target.closest('.row-hover[data-href]');
    if (!row || event.target.closest(OWN_ACTION)) return;
    window.location.href = row.dataset.href;
  });

  // Rows that opt into a tab stop (role="link" + tabindex) answer Enter too.
  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter') return;
    var row = event.target.closest('.row-hover[data-href][role="link"]');
    if (row) window.location.href = row.dataset.href;
  });
})();

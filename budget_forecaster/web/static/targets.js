// Progressive enhancement for the target edit page and management list.
// Everything degrades to plain links/forms when JS is off.

(function () {
  // Show period/end only when "recurring" is checked.
  function syncRecurring(toggle) {
    const on = toggle.checked;
    document.querySelectorAll(toggle.dataset.toggles).forEach(function (el) {
      el.hidden = !on;
      el.querySelectorAll('input, select').forEach(function (field) {
        field.disabled = !on;
      });
    });
  }

  document.querySelectorAll('#recurring-toggle').forEach(function (toggle) {
    syncRecurring(toggle);
    toggle.addEventListener('change', function () {
      syncRecurring(toggle);
    });
  });

  // Two-step inline delete confirm (no modal).
  document.querySelectorAll('[data-confirm]').forEach(function (form) {
    const trigger = form.querySelector('[data-delete-trigger]');
    const cluster = form.querySelector('.confirm-cluster');
    const cancel = form.querySelector('[data-delete-cancel]');
    if (!trigger || !cluster) return;
    trigger.addEventListener('click', function () {
      trigger.hidden = true;
      cluster.hidden = false;
      cluster.querySelector('[type=submit]').focus();
    });
    if (cancel) {
      cancel.addEventListener('click', function () {
        cluster.hidden = true;
        trigger.hidden = false;
        trigger.focus();
      });
    }
  });

  // Whole management row is clickable (the inner link keeps keyboard/no-JS access).
  document.querySelectorAll('.target-row[data-href]').forEach(function (row) {
    row.addEventListener('click', function (event) {
      if (event.target.closest('a')) return;
      window.location.href = row.dataset.href;
    });
    row.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') window.location.href = row.dataset.href;
    });
  });
})();

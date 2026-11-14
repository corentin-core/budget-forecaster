// A list page keeps its search in sight and folds the other filters behind one
// button, which counts the active ones. A checkbox marked data-filter-default
// is on by default, so it counts when unticked.
(function () {
  function activeCount(panel) {
    let count = 0;
    panel.querySelectorAll('input, select').forEach(function (field) {
      if (field.type === 'hidden' || field.disabled) return;
      if (field.type === 'checkbox') {
        if (field.checked !== field.hasAttribute('data-filter-default')) count += 1;
      } else if (field.value) {
        count += 1;
      }
    });
    return count;
  }

  document.querySelectorAll('[data-filter-toggle]').forEach(function (toggle) {
    const panel = document.getElementById(toggle.getAttribute('aria-controls'));
    const badge = toggle.querySelector('.filter-count');
    if (!panel || !badge) return;

    function sync() {
      const count = activeCount(panel);
      badge.textContent = String(count);
      badge.hidden = count === 0;
    }

    toggle.addEventListener('click', function () {
      panel.hidden = !panel.hidden;
      toggle.setAttribute('aria-expanded', String(!panel.hidden));
    });
    panel.addEventListener('change', sync);
    sync();
  });

  // With its button gone, a plain form applies each change as it is made.
  document.querySelectorAll('form[data-autosubmit]').forEach(function (form) {
    form.addEventListener('change', function () {
      form.requestSubmit();
    });
  });
})();

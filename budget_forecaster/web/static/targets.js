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

  // One primary action at a time: while the split section is open, Save would
  // submit the form above it and silently ignore the split fields.
  const splitSection = document.querySelector('[data-split-section]');
  const saveButton = document.querySelector('[data-save-button]');
  if (splitSection && saveButton) {
    const note = splitSection.querySelector('[data-split-note]');
    const syncSplit = function () {
      saveButton.disabled = splitSection.open;
      if (note) note.hidden = !splitSection.open;
    };
    syncSplit();
    splitSection.addEventListener('toggle', syncSplit);
  }

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

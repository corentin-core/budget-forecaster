// Two-step confirm on the overdue card. Rows come back from HTMX swaps, so the
// binding runs again after each swap instead of only at load.

(function () {
  function bind(root) {
    root.querySelectorAll('.overdue-item [data-confirm], .overdue-item[data-confirm]').forEach(function (holder) {
      const trigger = holder.querySelector('[data-delete-trigger]');
      const cluster = holder.querySelector('.confirm-cluster');
      const cancel = holder.querySelector('[data-delete-cancel]');
      if (!trigger || !cluster || trigger.dataset.bound) return;
      trigger.dataset.bound = '1';
      const strip = holder.closest('.overdue-actions');
      const siblings = strip
        ? Array.prototype.filter.call(strip.children, function (el) {
            return !el.contains(trigger);
          })
        : [];
      trigger.addEventListener('click', function () {
        trigger.hidden = true;
        siblings.forEach(function (el) {
          el.hidden = true;
        });
        cluster.hidden = false;
        cluster.querySelector('[type=submit]').focus();
      });
      if (cancel) {
        cancel.addEventListener('click', function () {
          cluster.hidden = true;
          trigger.hidden = false;
          siblings.forEach(function (el) {
            el.hidden = false;
          });
          trigger.focus();
        });
      }
    });
  }

  bind(document);
  document.body.addEventListener('htmx:afterSwap', function (event) {
    bind(event.target.parentElement || document);
  });
})();

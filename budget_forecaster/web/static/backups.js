// Two-step inline delete confirm for the Backups card. Delete needs JS (same
// pattern as the target edit page): the trigger reveals the confirm cluster.

(function () {
  document.querySelectorAll('.card [data-confirm]').forEach(function (form) {
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
})();

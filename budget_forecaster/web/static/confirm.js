// Two-step inline confirm, shared by every page that asks one.
//
// A holder marked data-confirm holds a trigger, a hidden .confirm-cluster and
// an optional cancel. Marking the surrounding action strip data-confirm-strip
// hides the other actions while the question is up. Clusters come back from
// HTMX swaps, so binding runs again after each one.
//
// data-confirm-keep leaves the trigger in place while the question is up, and
// makes it fold the question back: right when the trigger is what the question
// is about, such as the operation being linked.

(function () {
  let sequence = 0;

  function bind(root) {
    root.querySelectorAll('[data-confirm]').forEach(function (holder) {
      const trigger = holder.querySelector('[data-confirm-trigger]');
      const cluster = holder.querySelector('.confirm-cluster');
      const cancel = holder.querySelector('[data-confirm-cancel]');
      if (!trigger || !cluster || trigger.dataset.bound) return;
      trigger.dataset.bound = '1';

      if (!cluster.id) {
        sequence += 1;
        cluster.id = 'confirm-cluster-' + sequence;
      }
      trigger.setAttribute('aria-controls', cluster.id);
      trigger.setAttribute('aria-expanded', 'false');

      const strip = trigger.closest('[data-confirm-strip]');
      const siblings = strip
        ? Array.prototype.filter.call(strip.children, function (el) {
            return !el.contains(trigger);
          })
        : [];
      const keepTrigger = holder.hasAttribute('data-confirm-keep');

      function open(asking) {
        if (!keepTrigger) trigger.hidden = asking;
        trigger.setAttribute('aria-expanded', String(asking));
        cluster.hidden = !asking;
        siblings.forEach(function (el) {
          el.hidden = asking;
        });
      }

      trigger.addEventListener('click', function () {
        const asking = cluster.hidden;
        open(asking);
        if (asking) cluster.querySelector('[type=submit]').focus();
        else trigger.focus();
      });
      if (cancel) {
        cancel.addEventListener('click', function () {
          open(false);
          trigger.focus();
        });
      }
    });
  }

  bind(document);
  document.body.addEventListener('htmx:afterSwap', function () {
    bind(document);
  });
})();

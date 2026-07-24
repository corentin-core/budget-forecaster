// Bank picker: filter the list by name and enable submit once one is chosen.
(function () {
  const filter = document.getElementById('bank-filter');
  const submit = document.getElementById('bank-submit');
  const options = Array.from(document.querySelectorAll('.bank-option'));

  if (filter) {
    filter.addEventListener('input', function () {
      const query = filter.value.trim().toLowerCase();
      for (const option of options) {
        const match = option.dataset.name.includes(query);
        option.hidden = !match;
      }
    });
  }

  if (submit) {
    for (const option of options) {
      const radio = option.querySelector('input[type=radio]');
      radio.addEventListener('change', function () {
        submit.disabled = false;
      });
    }
  }
})();

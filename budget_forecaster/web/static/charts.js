// Interactive balance curve: a cursor, dot and tooltip that follow the pointer
// and read out the date and balance of the nearest sample.
(function () {
  'use strict';

  function setup() {
    var chart = document.getElementById('balance-chart');
    if (!chart) return;
    var dataEl = document.getElementById('balance-data');
    var points = JSON.parse(dataEl.textContent || '[]');
    if (points.length < 2) return;

    var svg = chart.querySelector('.sparkline');
    var cursor = chart.querySelector('.chart-cursor');
    var dot = chart.querySelector('.chart-dot');
    var tooltip = chart.querySelector('.chart-tooltip');
    var vbWidth = parseFloat(chart.dataset.width);
    var vbHeight = parseFloat(chart.dataset.height);

    function show() {
      cursor.hidden = false;
      dot.hidden = false;
      tooltip.hidden = false;
    }
    function hide() {
      cursor.hidden = true;
      dot.hidden = true;
      tooltip.hidden = true;
    }

    function move(clientX) {
      var rect = svg.getBoundingClientRect();
      var chartRect = chart.getBoundingClientRect();
      // Offset of the plot area within the chart (the y-axis gutter).
      var dx = rect.left - chartRect.left;
      var dy = rect.top - chartRect.top;
      var ratio = (clientX - rect.left) / rect.width;
      ratio = Math.max(0, Math.min(1, ratio));
      var index = Math.round(ratio * (points.length - 1));
      var point = points[index];
      var px = dx + (point.x / vbWidth) * rect.width;
      var py = dy + (point.y / vbHeight) * rect.height;

      cursor.style.left = px + 'px';
      dot.style.left = px + 'px';
      dot.style.top = py + 'px';
      tooltip.textContent = point.label + ' · ' + point.value;
      // Keep the tooltip inside the plot width.
      var half = tooltip.offsetWidth / 2;
      tooltip.style.left = Math.max(dx + half, Math.min(dx + rect.width - half, px)) + 'px';
      show();
    }

    svg.addEventListener('mousemove', function (e) {
      move(e.clientX);
    });
    svg.addEventListener('mouseleave', hide);
    svg.addEventListener('touchstart', function (e) {
      move(e.touches[0].clientX);
    });
    svg.addEventListener('touchmove', function (e) {
      move(e.touches[0].clientX);
      e.preventDefault();
    });
    svg.addEventListener('touchend', hide);
  }

  function setupDonut() {
    var donut = document.getElementById('expense-donut');
    if (!donut) return;
    var group = donut.querySelector('.slices');
    var slices = donut.querySelectorAll('.slice');
    var tooltip = donut.querySelector('.donut-tooltip');

    function fill(slice) {
      tooltip.textContent = '';
      var title = document.createElement('strong');
      title.textContent = slice.dataset.label;
      var detail = document.createElement('div');
      detail.textContent = slice.dataset.detail;
      var avg = document.createElement('div');
      avg.className = 'tt-muted';
      avg.textContent = slice.dataset.average;
      tooltip.appendChild(title);
      tooltip.appendChild(detail);
      tooltip.appendChild(avg);
    }

    function place(clientX, clientY) {
      var rect = donut.getBoundingClientRect();
      var x = clientX - rect.left;
      var y = clientY - rect.top;
      var half = tooltip.offsetWidth / 2;
      tooltip.style.left = Math.max(half, Math.min(rect.width - half, x)) + 'px';
      tooltip.style.top = y + 'px';
    }

    function activate(slice) {
      group.classList.add('faded');
      slices.forEach(function (s) {
        s.classList.toggle('active', s === slice);
      });
      fill(slice);
      tooltip.hidden = false;
    }
    function clear() {
      group.classList.remove('faded');
      slices.forEach(function (s) {
        s.classList.remove('active');
      });
      tooltip.hidden = true;
    }

    slices.forEach(function (slice) {
      slice.addEventListener('mouseenter', function () {
        activate(slice);
      });
      slice.addEventListener('mousemove', function (e) {
        place(e.clientX, e.clientY);
      });
      slice.addEventListener('mouseleave', clear);
      slice.addEventListener('click', function (e) {
        activate(slice);
        place(e.clientX, e.clientY);
      });
    });
    donut.addEventListener('mouseleave', clear);
  }

  function init() {
    setup();
    setupDonut();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Re-wire the donut after HTMX swaps in a fresh breakdown (period change).
  document.body.addEventListener('htmx:afterSwap', function () {
    setupDonut();
  });
})();

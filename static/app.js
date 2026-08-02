/* APEXFIN dashboard runtime.
 * - Reads the injected datapack (id=apexfin-datapack) and renders ECharts.
 * - ECharts theme is derived from CSS custom properties so charts follow the
 *   active theme (dark / light / CVD) and the dual-channel color protocol.
 * - Offline degradation: if echarts failed to load, the server-rendered
 *   <details class="chart-fallback"> tables stay open and a notice is shown.
 * No emoji. Market colors (--mkt-*) only reach candlestick + volume via theme.
 */
(function () {
  'use strict';

  var root = document.documentElement;
  var STORE_KEY = 'apexfin-theme';

  function cssv(name) {
    return getComputedStyle(root).getPropertyValue(name).trim();
  }

  /* ---- Theme -------------------------------------------------------------- */
  function applyTheme(theme) {
    if (theme !== 'light' && theme !== 'dark') theme = 'dark';
    root.setAttribute('data-theme', theme);
    var btns = document.querySelectorAll('.theme-toggle button[data-theme-set]');
    btns.forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-theme-set') === theme ? 'true' : 'false');
    });
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem(STORE_KEY); } catch (e) {}
    applyTheme(saved || root.getAttribute('data-theme') || 'dark');
    document.querySelectorAll('.theme-toggle button[data-theme-set]').forEach(function (b) {
      b.addEventListener('click', function () {
        var t = b.getAttribute('data-theme-set');
        applyTheme(t);
        try { localStorage.setItem(STORE_KEY, t); } catch (e) {}
        rebuildCharts();
      });
    });
  }

  /* ---- ECharts theme from CSS vars --------------------------------------- */
  function buildTheme() {
    return {
      color: [cssv('--chart-1'), cssv('--chart-2'), cssv('--chart-3'),
              cssv('--chart-4'), cssv('--chart-5'), cssv('--chart-6')],
      backgroundColor: 'transparent',
      textStyle: { fontFamily: cssv('--font-ui'), fontSize: 12 },
      animation: false,
      grid: { left: 8, right: 8, top: 16, bottom: 8, containLabel: true },
      categoryAxis: {
        axisLine: { lineStyle: { color: cssv('--chart-axis') } },
        axisTick: { show: false },
        axisLabel: { color: cssv('--chart-label'), fontFamily: cssv('--font-data'), fontSize: 11 },
        splitLine: { show: false }
      },
      valueAxis: {
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: cssv('--chart-label'), fontFamily: cssv('--font-data'), fontSize: 11 },
        splitLine: { lineStyle: { color: cssv('--chart-split'), width: 1 } }
      },
      candlestick: {
        itemStyle: {
          color: cssv('--mkt-up'), color0: cssv('--mkt-down'),
          borderColor: cssv('--mkt-up'), borderColor0: cssv('--mkt-down'), borderWidth: 1
        }
      },
      line: { symbol: 'none', lineStyle: { width: 1.5 }, smooth: false },
      bar: { itemStyle: { borderRadius: [2, 2, 0, 0] } },
      tooltip: {
        backgroundColor: cssv('--chart-tooltip-bg'),
        borderColor: cssv('--border-strong'), borderWidth: 1, padding: [8, 10],
        textStyle: { color: cssv('--fg'), fontFamily: cssv('--font-data'), fontSize: 12 },
        axisPointer: {
          type: 'cross',
          lineStyle: { color: cssv('--chart-crosshair'), width: 1, type: 'dashed' },
          crossStyle: { color: cssv('--chart-crosshair'), width: 1, type: 'dashed' },
          label: { backgroundColor: cssv('--surface-3'), color: cssv('--fg'),
                   fontFamily: cssv('--font-data'), borderColor: cssv('--border-strong') }
        }
      },
      legend: { textStyle: { color: cssv('--muted'), fontSize: 11 }, icon: 'roundRect', itemWidth: 10, itemHeight: 2 }
    };
  }

  /* ---- Chart lifecycle ---------------------------------------------------- */
  var charts = [];   // { id, inst }
  var datapack = null;

  function clearCharts() {
    charts.forEach(function (c) { try { c.inst.dispose(); } catch (e) {} });
    charts = [];
  }

  function buildCharts() {
    if (typeof echarts === 'undefined' || !datapack || !datapack.charts) return;
    echarts.registerTheme('apexfin', buildTheme());
    datapack.charts.forEach(function (spec) {
      var el = document.getElementById('chart-' + spec.chart_id);
      if (!el) return;
      var inst = echarts.init(el, 'apexfin', { renderer: 'canvas' });
      try {
        inst.setOption(spec.option || {});
        charts.push({ id: spec.chart_id, inst: inst });
      } catch (e) {
        // Corrupt option: fall back to the data table.
        el.style.display = 'none';
      }
    });
    // JS is available: collapse server-open fallback tables now that charts render.
    document.querySelectorAll('.chart-fallback[open]').forEach(function (d) { d.removeAttribute('open'); });
  }

  function degradeCharts() {
    document.querySelectorAll('.chart').forEach(function (box) {
      box.style.display = 'none';
    });
    document.querySelectorAll('.chart-fallback').forEach(function (d) {
      d.setAttribute('open', '');
      if (!d.parentNode.querySelector('.degrade-note')) {
        var note = document.createElement('div');
        note.className = 'degrade-note';
        note.textContent = '图表引擎未加载，已降级为数据表。';
        d.parentNode.insertBefore(note, d);
      }
    });
  }

  function rebuildCharts() {
    clearCharts();
    if (typeof echarts === 'undefined') { degradeCharts(); return; }
    buildCharts();
  }

  function resizeCharts() {
    charts.forEach(function (c) { try { c.inst.resize(); } catch (e) {} });
  }

  /* ---- Boot --------------------------------------------------------------- */
  function boot() {
    var node = document.getElementById('apexfin-datapack');
    if (node) {
      try { datapack = JSON.parse(node.textContent || '{}'); }
      catch (e) { datapack = null; }
    }
    initTheme();
    if (typeof echarts === 'undefined') {
      degradeCharts();
    } else {
      buildCharts();
    }
    var rt;
    window.addEventListener('resize', function () {
      clearTimeout(rt);
      rt = setTimeout(resizeCharts, 150);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();

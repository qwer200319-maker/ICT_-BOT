const DEFAULT_API_BASE = (window.API_BASE || localStorage.getItem('API_BASE') || '').trim();
const DEFAULT_WS_BASE = (window.WS_BASE || localStorage.getItem('WS_BASE') || 'wss://stream.binance.com:9443').trim();
const MAX_BARS = 200;

const pairSelect = document.getElementById('pairSelect');
const statusEl = document.getElementById('status');
const refreshBtn = document.getElementById('refreshBtn');
const signalsTable = document.getElementById('signalsTable');
const signalsBody = signalsTable.querySelector('tbody');
const signalsEmpty = document.getElementById('signalsEmpty');
const tfButtons = document.getElementById('tfButtons');
const fullscreenBtn = document.getElementById('fullscreenBtn');
const toggleSignalsBtn = document.getElementById('toggleSignalsBtn');
const signalsPanel = document.getElementById('signalsPanel');
const toggleFvgBtn = document.getElementById('toggleFvgBtn');
const toggleLiqBtn = document.getElementById('toggleLiqBtn');
const chartEl = document.getElementById('chartMain');
const chartWrap = document.getElementById('chartWrap');
const fsToolbar = document.getElementById('fsToolbar');
const fsPairSelect = document.getElementById('fsPairSelect');
const fsTfButtons = document.getElementById('fsTfButtons');
const fsToggleFvg = document.getElementById('fsToggleFvg');
const fsToggleLiq = document.getElementById('fsToggleLiq');
const fsExitBtn = document.getElementById('fsExitBtn');
const apiBtn = document.getElementById('apiBtn');
const apiPanel = document.getElementById('apiPanel');
const apiBaseInput = document.getElementById('apiBaseInput');
const apiSaveBtn = document.getElementById('apiSaveBtn');
const installBtn = document.getElementById('installBtn');

let apiBase = DEFAULT_API_BASE;
let wsBase = DEFAULT_WS_BASE;
let timeframes = [];
let pairs = [];
let currentTf = '5m';
let signalsVisible = true;
let showFvg = false;
let showLiq = false;
let lastInteraction = 0;
let deferredInstallPrompt = null;
let lastSnapshotTs = {};
let snapshotAbort = null;
let lastSnapshotData = null;
let ws = null;
let wsConnected = false;
let wsReconnectTimer = null;
let wsBackoffMs = 1000;
let lastWsKey = '';
let wsRenderTimer = null;
let statusBaseText = '';

const plotlyConfig = {
  responsive: true,
  displaylogo: false,
  displayModeBar: 'hover',
  scrollZoom: true,
  doubleClick: 'reset',
  modeBarButtonsToRemove: ['select2d', 'lasso2d', 'toImage']
};

function updateStatus() {
  const liveTag = wsConnected ? ' | LIVE' : '';
  statusEl.textContent = statusBaseText + liveTag;
}

function setStatus(text) {
  statusBaseText = text;
  updateStatus();
}

function showApiPanel(show) {
  apiPanel.classList.toggle('hidden', !show);
}

function normalizeBase(url) {
  return url.replace(/\/$/, '');
}

function requireBase() {
  if (!apiBase) {
    showApiPanel(true);
    setStatus('Set Backend API Base (HTTPS)');
    return false;
  }
  return true;
}

function fillPairs(selectEl) {
  selectEl.innerHTML = '';
  pairs.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = p;
    selectEl.appendChild(opt);
  });
}

function renderTfButtons(container, onClick) {
  container.innerHTML = '';
  timeframes.forEach(tf => {
    const btn = document.createElement('button');
    btn.className = `tf-btn ${tf === currentTf ? 'active' : ''}`;
    btn.textContent = tf.toUpperCase();
    btn.addEventListener('click', () => onClick(tf));
    container.appendChild(btn);
  });
}

function updateToggleStyles() {
  toggleFvgBtn.classList.toggle('active', showFvg);
  toggleLiqBtn.classList.toggle('active', showLiq);
  fsToggleFvg.classList.toggle('active', showFvg);
  fsToggleLiq.classList.toggle('active', showLiq);
}

async function fetchJson(path, options = {}) {
  try {
    const res = await fetch(`${apiBase}${path}`, { signal: options.signal, cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showApiPanel(false);
    return await res.json();
  } catch (err) {
    if (err && err.name === 'AbortError') return null;
    setStatus(`API error: ${err.message}`);
    showApiPanel(true);
    return null;
  }
}

function cacheSnapshot(key, data) {
  try { localStorage.setItem(key, JSON.stringify(data)); } catch (e) {}
}

function loadCachedSnapshot(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function fmtTime(ms) {
  return new Date(ms).toISOString().replace('.000Z', 'Z');
}

function closeWs() {
  if (ws) {
    try {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
      ws.close();
    } catch (e) {}
  }
  ws = null;
  wsConnected = false;
  updateStatus();
}

function scheduleReconnect() {
  if (wsReconnectTimer) return;
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    connectWs();
  }, wsBackoffMs);
  wsBackoffMs = Math.min(Math.floor(wsBackoffMs * 1.5), 15000);
}

function handleWsMessage(raw) {
  let msg;
  try { msg = JSON.parse(raw); } catch (e) { return; }
  if (!msg.k || !lastSnapshotData || !lastSnapshotData.ohlc) return;

  const k = msg.k;
  const ts = fmtTime(k.t);
  const ohlc = lastSnapshotData.ohlc;

  const lastIdx = ohlc.time.length - 1;
  if (lastIdx >= 0 && ohlc.time[lastIdx] === ts) {
    ohlc.open[lastIdx] = Number(k.o);
    ohlc.high[lastIdx] = Number(k.h);
    ohlc.low[lastIdx] = Number(k.l);
    ohlc.close[lastIdx] = Number(k.c);
  } else {
    ohlc.time.push(ts);
    ohlc.open.push(Number(k.o));
    ohlc.high.push(Number(k.h));
    ohlc.low.push(Number(k.l));
    ohlc.close.push(Number(k.c));
    if (ohlc.time.length > MAX_BARS) {
      ohlc.time.shift();
      ohlc.open.shift();
      ohlc.high.shift();
      ohlc.low.shift();
      ohlc.close.shift();
    }
  }

  const cacheKey = `snapshot:${pairSelect.value}:${currentTf}`;
  lastSnapshotTs[cacheKey] = ts;

  if (!wsRenderTimer) {
    wsRenderTimer = setTimeout(() => {
      wsRenderTimer = null;
      renderSnapshot(lastSnapshotData);
    }, 300);
  }
}

function connectWs() {
  if (!pairSelect.value || !currentTf) return;
  const key = `${pairSelect.value.toLowerCase()}@kline_${currentTf}`;
  if (lastWsKey === key && ws) return;

  closeWs();
  lastWsKey = key;
  wsBackoffMs = 1000;

  const base = wsBase.replace(/\/$/, '');
  const url = `${base}/ws/${key}`;

  try {
    ws = new WebSocket(url);
  } catch (e) {
    return;
  }

  ws.onopen = () => {
    wsConnected = true;
    updateStatus();
  };

  ws.onmessage = (ev) => handleWsMessage(ev.data);

  ws.onclose = () => {
    wsConnected = false;
    updateStatus();
    scheduleReconnect();
  };

  ws.onerror = () => {
    wsConnected = false;
    updateStatus();
    try { ws.close(); } catch (e) {}
  };
}

async function loadConfig() {
  if (!requireBase()) return;
  const data = await fetchJson('/api/scan_all');
  if (!data) return;
  pairs = data.pairs || [];
  timeframes = ['1h','15m','5m'];
  currentTf = timeframes.includes('15m') ? '15m' : (timeframes[0] || '5m');
  fillPairs(pairSelect);
  fillPairs(fsPairSelect);
  renderAllTf();
}

function renderAllTf() {
  renderTfButtons(tfButtons, (tf) => { currentTf = tf; renderAllTf(); loadPair(); });
  renderTfButtons(fsTfButtons, (tf) => { currentTf = tf; renderAllTf(); loadPair(); });
}

async function loadSignals() {
  if (!requireBase()) return;
  const data = await fetchJson('/api/scan_all');
  if (!data) return;
  const sessionText = data.session_ok ? 'Session ON' : 'Session OFF';
  setStatus(sessionText);

  signalsBody.innerHTML = '';
  if (!data.signals || data.signals.length === 0) {
    signalsTable.classList.add('hidden');
    signalsEmpty.style.display = 'block';
    return;
  }
  signalsEmpty.style.display = 'none';
  signalsTable.classList.remove('hidden');
  data.signals.forEach(s => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${s.pair}</td>
      <td style="color:${s.direction === 'LONG' ? 'var(--green)' : 'var(--red)'}">${s.direction}</td>
      <td>${s.entry.toFixed(6)}</td>
      <td>${s.stop_loss.toFixed(6)}</td>
      <td>${s.take_profit.toFixed(6)}</td>
      <td>${s.risk_reward.toFixed(2)}</td>
      <td>${s.reason}</td>
      <td>${s.timestamp_utc}</td>
    `;
    signalsBody.appendChild(tr);
  });
}

function makeCandles(ohlc, title) {
  const parsed = ohlc.time.map(t => new Date(t));
  const validDates = parsed.every(d => !isNaN(d.getTime()));
  const times = validDates ? parsed : ohlc.time.map((_, i) => i);
  const x0 = times[0];
  const x1 = times[times.length - 1];
  const open = ohlc.open.map(Number);
  const high = ohlc.high.map(Number);
  const low = ohlc.low.map(Number);
  const close = ohlc.close.map(Number);

  return {
    data: [
      {
        x: times,
        open,
        high,
        low,
        close,
        type: 'candlestick',
        increasing: { line: { color: '#26a69a', width: 1 }, fillcolor: '#26a69a' },
        decreasing: { line: { color: '#ef5350', width: 1 }, fillcolor: '#ef5350' },
        whiskerwidth: 0.6
      }
    ],
    layout: {
      title: { text: title, font: { size: 12, color: '#8a8f98' } },
      hovermode: 'x',
      dragmode: 'pan',
      uirevision: `${pairSelect.value}-${currentTf}`,
      xaxis: {
        type: validDates ? 'date' : 'linear',
        range: validDates ? [x0, x1] : undefined,
        rangeslider: { visible: false },
        showgrid: true,
        gridcolor: '#2a2e39',
        showline: true,
        linecolor: '#2a2e39',
        showspikes: true,
        spikemode: 'across',
        spikesnap: 'cursor',
        spikecolor: '#8a8f98',
        spikethickness: 1
      },
      yaxis: {
        showgrid: true,
        gridcolor: '#2a2e39',
        showline: true,
        linecolor: '#2a2e39',
        showspikes: true,
        spikemode: 'across',
        spikecolor: '#8a8f98',
        spikethickness: 1
      },
      margin: { l: 55, r: 15, t: 28, b: 30 },
      paper_bgcolor: '#131722',
      plot_bgcolor: '#131722',
      font: { color: '#d1d4dc' }
    },
    _times: times
  };
}

function buildLevelShapes(times, levels) {
  if (!levels || levels.length === 0) return [];
  const x0 = times[0];
  const x1 = times[times.length - 1];
  return levels.map(l => ({
    type: 'line',
    x0, x1,
    y0: l.level, y1: l.level,
    line: { color: l.color || '#888', width: 1 },
    opacity: 0.5,
    layer: 'below'
  }));
}

function buildFvgShapes(times, fvgs) {
  const shapes = [];
  const recent = fvgs.slice(-3);
  recent.forEach(z => {
    const x0 = times[Math.max(z.index - 2, 0)];
    const x1 = times[times.length - 1];
    const color = z.direction === 'bullish' ? 'rgba(38,166,154,0.10)' : 'rgba(239,83,80,0.10)';
    shapes.push({ type: 'rect', x0, x1, y0: z.lower, y1: z.upper, fillcolor: color, line: { width: 0 }, layer: 'below' });
  });
  return shapes;
}

function renderSnapshot(data) {
  const title = `${data.pair} - ${data.tf.toUpperCase()}`;
  const chart = makeCandles(data.ohlc, title);

  const shapes = [];
  if (showLiq) {
    const levels = [];
    data.pools.slice(-5).forEach(p => levels.push({ level: p.level, color: '#3f7cff' }));
    if (data.sweep) {
      levels.push({ level: data.sweep.level, color: data.sweep.direction === 'bearish' ? '#ef5350' : '#26a69a' });
    }
    shapes.push(...buildLevelShapes(chart._times, levels));
  }

  if (showFvg) {
    shapes.push(...buildFvgShapes(chart._times, data.fvgs));
  }

  chart.layout.shapes = shapes;
  Plotly.react('chartMain', chart.data, chart.layout, plotlyConfig);
  lastSnapshotData = data;
}

async function loadPair() {
  if (!requireBase()) return;
  const pair = pairSelect.value;
  const cacheKey = `snapshot:${pair}:${currentTf}`;

  const cached = loadCachedSnapshot(cacheKey);
  if (cached && cached.ohlc && cached.ohlc.time) {
    renderSnapshot(cached);
  }

  const since = lastSnapshotTs[cacheKey] || '';
  const params = new URLSearchParams({
    pair,
    tf: currentTf,
    fvg: showFvg ? '1' : '0',
    liq: showLiq ? '1' : '0'
  });
  if (since) params.set('since', since);

  if (snapshotAbort) snapshotAbort.abort();
  snapshotAbort = new AbortController();

  const data = await fetchJson(`/api/snapshot?${params.toString()}`, { signal: snapshotAbort.signal });
  if (!data) return;

  if (data.not_modified) {
    const lastTs = data.last || since;
    setStatus(`Session ${data.session_ok ? 'ON' : 'OFF'} | ${pair} ${currentTf.toUpperCase()} | Last: ${lastTs}`);
    connectWs();
    return;
  }

  if (!data.ok) {
    setStatus(`No data for ${pair}`);
    Plotly.purge('chartMain');
    closeWs();
    return;
  }

  const lastTs = data.ohlc.time[data.ohlc.time.length - 1] || '';
  if (lastSnapshotTs[cacheKey] === lastTs) {
    const staleTag = data.stale ? ' | Stale' : '';
    setStatus(`Session ${data.session_ok ? 'ON' : 'OFF'} | ${pair} ${currentTf.toUpperCase()} | ${data.ohlc.time.length} candles | Last: ${lastTs}${staleTag}`);
    connectWs();
    return;
  }
  lastSnapshotTs[cacheKey] = lastTs;

  cacheSnapshot(cacheKey, data);
  renderSnapshot(data);

  const staleTag = data.stale ? ' | Stale' : '';
  setStatus(`Session ${data.session_ok ? 'ON' : 'OFF'} | ${pair} ${currentTf.toUpperCase()} | ${data.ohlc.time.length} candles | Last: ${lastTs}${staleTag}`);
  connectWs();
}

async function refreshAll() {
  const now = Date.now();
  if (now - lastInteraction < 1200) {
    await loadSignals();
    return;
  }
  await loadSignals();
  await loadPair();
}

fullscreenBtn.addEventListener('click', () => {
  if (chartWrap.requestFullscreen) chartWrap.requestFullscreen();
});

fsExitBtn.addEventListener('click', () => {
  if (document.fullscreenElement) document.exitFullscreen();
});

document.addEventListener('fullscreenchange', () => {
  const isFs = !!document.fullscreenElement;
  fsToolbar.classList.toggle('show', isFs);
});

toggleSignalsBtn.addEventListener('click', () => {
  signalsVisible = !signalsVisible;
  signalsPanel.style.display = signalsVisible ? 'block' : 'none';
});

toggleFvgBtn.addEventListener('click', () => {
  showFvg = !showFvg;
  updateToggleStyles();
  loadPair();
});

toggleLiqBtn.addEventListener('click', () => {
  showLiq = !showLiq;
  updateToggleStyles();
  loadPair();
});

fsToggleFvg.addEventListener('click', () => {
  showFvg = !showFvg;
  updateToggleStyles();
  loadPair();
});

fsToggleLiq.addEventListener('click', () => {
  showLiq = !showLiq;
  updateToggleStyles();
  loadPair();
});

fsPairSelect.addEventListener('change', () => {
  pairSelect.value = fsPairSelect.value;
  loadPair();
});

apiBtn.addEventListener('click', () => {
  apiPanel.classList.toggle('hidden');
});

apiSaveBtn.addEventListener('click', async () => {
  apiBase = normalizeBase(apiBaseInput.value.trim());
  if (!apiBase) return;
  localStorage.setItem('API_BASE', apiBase);
  closeWs();
  await loadConfig();
  await refreshAll();
});

refreshBtn.addEventListener('click', () => {
  refreshAll();
});

chartEl.addEventListener('wheel', () => { lastInteraction = Date.now(); }, { passive: true });
chartEl.addEventListener('mousedown', () => { lastInteraction = Date.now(); });
chartEl.addEventListener('touchstart', () => { lastInteraction = Date.now(); }, { passive: true });

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  installBtn.classList.remove('hidden');
});

installBtn.addEventListener('click', async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  await deferredInstallPrompt.userChoice;
  deferredInstallPrompt = null;
  installBtn.classList.add('hidden');
});

window.addEventListener('appinstalled', () => {
  installBtn.classList.add('hidden');
});

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('service-worker.js').then((reg) => {
    reg.addEventListener('updatefound', () => {
      const newWorker = reg.installing;
      if (!newWorker) return;
      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
          window.location.reload();
        }
      });
    });
  });
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    window.location.reload();
  });
}

apiBaseInput.value = apiBase;

(async () => {
  if (apiBase) {
    await loadConfig();
    await refreshAll();
  } else {
    showApiPanel(true);
    setStatus('Set Backend API Base');
  }
})();

setInterval(refreshAll, 20000);

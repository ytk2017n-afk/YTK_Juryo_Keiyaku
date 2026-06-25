/**
 * 手書きCanvas管理 - Apple Pencil / タッチ対応
 * 手書きフィールド: 本名(c_realname)、キャスト名(c_alias)、署名(c_sig) の3箇所のみ
 */

let penSize  = 2;
let penColor = '#1A237E';
const DPR    = window.devicePixelRatio || 1;

const FIELD_IDS = ['c_realname', 'c_sig'];

// ── Canvas初期化 ─────────────────────────────────────────────────────────────
function initCanvas(canvas) {
  const wrap = canvas.parentElement;
  const rect = wrap.getBoundingClientRect();
  const w = Math.max(rect.width,  100);
  const h = Math.max(rect.height, 40);

  canvas.width  = w * DPR;
  canvas.height = h * DPR;
  canvas.style.width  = w + 'px';
  canvas.style.height = h + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(DPR, DPR);
  ctx.lineCap    = 'round';
  ctx.lineJoin   = 'round';
  ctx.strokeStyle = penColor;
  ctx.lineWidth   = penSize;
}

function initAllCanvases() {
  FIELD_IDS.forEach(id => {
    const c = document.getElementById(id);
    if (c) initCanvas(c);
  });
}

// ── 描画イベント ─────────────────────────────────────────────────────────────
function attachDrawEvents(canvas) {
  let drawing = false;

  function getXY(e) {
    const rect = canvas.getBoundingClientRect();
    const src  = e.touches ? e.touches[0] : e;
    return { x: src.clientX - rect.left, y: src.clientY - rect.top };
  }

  function start(e) {
    drawing = true;
    const { x, y } = getXY(e);
    const ctx = canvas.getContext('2d');
    ctx.strokeStyle = penColor;
    ctx.lineWidth = e.pressure > 0 ? penSize * (0.5 + e.pressure * 1.5) : penSize;
    ctx.beginPath();
    ctx.moveTo(x, y);
    e.preventDefault();
  }

  function move(e) {
    if (!drawing) return;
    e.preventDefault();
    const { x, y } = getXY(e);
    const ctx = canvas.getContext('2d');
    ctx.strokeStyle = penColor;
    ctx.lineWidth = e.pressure > 0 ? penSize * (0.5 + e.pressure * 1.5) : penSize;
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x, y);
  }

  function end() {
    drawing = false;
    canvas.getContext('2d').beginPath();
  }

  canvas.addEventListener('pointerdown', start, { passive: false });
  canvas.addEventListener('pointermove', move,  { passive: false });
  canvas.addEventListener('pointerup',   end);
  canvas.addEventListener('pointerleave', end);
  canvas.addEventListener('pointercancel', end);
  canvas.addEventListener('touchstart', start, { passive: false });
  canvas.addEventListener('touchmove',  move,  { passive: false });
  canvas.addEventListener('touchend',   end);
}

function attachAllDrawEvents() {
  FIELD_IDS.forEach(id => {
    const c = document.getElementById(id);
    if (c) attachDrawEvents(c);
  });
}

// ── ペン設定 ─────────────────────────────────────────────────────────────────
function setPenSize(size, btn) {
  penSize = size;
  document.querySelectorAll('.pen-size-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

function setPenColor(color, btn) {
  penColor = color;
  document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

// ── フィールド消去 ───────────────────────────────────────────────────────────
function clearField(canvasId) {
  const c = document.getElementById(canvasId);
  if (!c) return;
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);
}

function clearAllFields() {
  if (!confirm('手書きフィールドの内容を全消去しますか？')) return;
  FIELD_IDS.forEach(id => clearField(id));
}

// ── 消費税自動計算 ────────────────────────────────────────────────────────────
function calcTax() {
  const raw = document.getElementById('inputAmount').value.replace(/[,，¥\s]/g, '');
  const amount = parseFloat(raw);
  if (isNaN(amount) || amount <= 0) {
    document.getElementById('taxDisplay').textContent   = '―';
    document.getElementById('totalDisplay').textContent = '―';
    return;
  }
  const tax   = Math.floor(amount * 0.1);
  const total = amount + tax;
  document.getElementById('taxDisplay').textContent   = tax.toLocaleString();
  document.getElementById('totalDisplay').textContent = total.toLocaleString();
}

// ── 日付フォーマット ──────────────────────────────────────────────────────────
function formatDateJP(isoDate) {
  if (!isoDate) return '';
  const [y, m, d] = isoDate.split('-');
  return `${y}年${parseInt(m)}月${parseInt(d)}日`;
}

// ── Canvas空判定 ─────────────────────────────────────────────────────────────
function isCanvasEmpty(canvas) {
  const blank = document.createElement('canvas');
  blank.width  = canvas.width;
  blank.height = canvas.height;
  return canvas.toDataURL() === blank.toDataURL();
}

// ── 送信処理 ─────────────────────────────────────────────────────────────────
let _submitting = false;
async function submitReceipt() {
  if (_submitting) return;

  const alias     = document.getElementById('inputAlias').value.trim();
  const amountRaw = document.getElementById('inputAmount').value.replace(/[,，¥\s]/g, '');
  const amount    = parseFloat(amountRaw) || 0;

  if (!alias) {
    alert('キャスト名を入力してください。');
    document.getElementById('inputAlias').focus();
    return;
  }
  if (amount <= 0) {
    alert('金額を入力してください。');
    document.getElementById('inputAmount').focus();
    return;
  }

  _submitting = true;
  const overlay = document.getElementById('loadingOverlay');
  overlay.style.display = 'flex';

  // 手書き画像
  const canvasData = {};
  FIELD_IDS.forEach(id => {
    const c = document.getElementById(id);
    if (!c) return;
    canvasData[id.replace('c_', '')] = isCanvasEmpty(c) ? '' : c.toDataURL('image/png');
  });

  const tax   = Math.floor(amount * 0.1);
  const total     = amount + tax;

  const dateIso  = document.getElementById('receiptDate').value;
  const dateText = formatDateJP(dateIso);

  const payload = {
    ...canvasData,
    date:    dateText,
    alias:   document.getElementById('inputAlias').value,
    address: document.getElementById('inputAddress').value,
    phone:   document.getElementById('inputPhone').value,
    amount:  amount > 0 ? amount.toLocaleString() : '',
    tax:     amount > 0 ? tax.toLocaleString()    : '',
    total:   amount > 0 ? total.toLocaleString()  : '',
    desc:    document.getElementById('inputDesc').value,
  };

  try {
    const res = await fetch('/receipt/submit-handwriting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      window.location.href = `/receipt/complete/${data.receipt_id}`;
    } else {
      _submitting = false;
      overlay.style.display = 'none';
      const err = await res.text();
      alert('送信に失敗しました。\n' + err);
    }
  } catch (e) {
    _submitting = false;
    overlay.style.display = 'none';
    alert('通信エラーが発生しました。\nネットワーク接続を確認してください。');
  }
}

// ── リサイズ対応 ─────────────────────────────────────────────────────────────
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    FIELD_IDS.forEach(id => {
      const c = document.getElementById(id);
      if (!c) return;
      const img = c.toDataURL();
      initCanvas(c);
      if (img !== document.createElement('canvas').toDataURL()) {
        const image = new Image();
        const wrap  = c.parentElement;
        image.onload = () => {
          c.getContext('2d').drawImage(image, 0, 0, wrap.clientWidth, wrap.clientHeight);
        };
        image.src = img;
      }
    });
  }, 200);
});

// ── 起動 ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initAllCanvases();
  attachAllDrawEvents();
});

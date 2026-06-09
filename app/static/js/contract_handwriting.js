/**
 * 契約書手書きCanvas管理 - Apple Pencil / タッチ対応
 */

let penSize  = 2;
let penColor = '#1A237E';
const DPR    = window.devicePixelRatio || 1;

const FIELD_IDS = [
  'c_oto_preamble',
  'c_date',
  'c_oto_addr',
  'c_oto_realname',
  'c_oto_alias',
];

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

  canvas.addEventListener('pointerdown',  start, { passive: false });
  canvas.addEventListener('pointermove',  move,  { passive: false });
  canvas.addEventListener('pointerup',    end);
  canvas.addEventListener('pointerleave', end);
  canvas.addEventListener('pointercancel',end);
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
  c.getContext('2d').clearRect(0, 0, c.width, c.height);
}

function clearAllFields() {
  if (!confirm('全フィールドの手書き内容を消去しますか？')) return;
  FIELD_IDS.forEach(id => clearField(id));
}

// ── 送信処理 ─────────────────────────────────────────────────────────────────
function isCanvasEmpty(canvas) {
  const blank = document.createElement('canvas');
  blank.width  = canvas.width;
  blank.height = canvas.height;
  return canvas.toDataURL() === blank.toDataURL();
}

async function submitContract() {
  const overlay = document.getElementById('loadingOverlay');
  overlay.style.display = 'flex';

  const fields = {};
  FIELD_IDS.forEach(id => {
    const c = document.getElementById(id);
    if (!c) return;
    // c_oto_preamble → oto_preamble のようにプレフィックス c_ を除去
    const key = id.replace(/^c_/, '');
    fields[key] = isCanvasEmpty(c) ? '' : c.toDataURL('image/png');
  });

  try {
    const res = await fetch('/contract/submit', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(fields),
    });

    if (res.ok) {
      const data = await res.json();
      window.location.href = `/contract/complete/${data.contract_id}`;
    } else {
      overlay.style.display = 'none';
      alert('送信に失敗しました。\n' + await res.text());
    }
  } catch (e) {
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

// ── 条文トグルのアイコン切り替え ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initAllCanvases();
  attachAllDrawEvents();

  const toggle = document.querySelector('.articles-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      toggle.classList.toggle('collapsed');
    });
  }
});

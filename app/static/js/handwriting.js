/**
 * 手書きCanvas管理 - Apple Pencil / タッチ対応
 */

// ── グローバル設定 ───────────────────────────────────────────────────────────
let penSize  = 2;
let penColor = '#1A237E';
const DPR    = window.devicePixelRatio || 1;

// フィールドID一覧
const FIELD_IDS = [
  'c_atena','c_date','c_invoice','c_shopname',
  'c_alias','c_realname','c_addr1','c_addr2',
  'c_amount','c_tax','c_total','c_desc','c_sig'
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
  let lastX = 0, lastY = 0;

  function getXY(e) {
    const rect = canvas.getBoundingClientRect();
    const src  = e.touches ? e.touches[0] : e;
    return { x: src.clientX - rect.left, y: src.clientY - rect.top };
  }

  function start(e) {
    // Apple PencilはpointerType='pen'、指はtouch/mouse
    drawing = true;
    const { x, y } = getXY(e);
    lastX = x; lastY = y;

    const ctx = canvas.getContext('2d');
    ctx.strokeStyle = penColor;
    // 圧力感知（Apple Pencil）
    ctx.lineWidth = e.pressure > 0
      ? penSize * (0.5 + e.pressure * 1.5)
      : penSize;
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
    ctx.lineWidth = e.pressure > 0
      ? penSize * (0.5 + e.pressure * 1.5)
      : penSize;
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x, y);
    lastX = x; lastY = y;
  }

  function end() {
    drawing = false;
    const ctx = canvas.getContext('2d');
    ctx.beginPath();
  }

  // Pointer Events（Apple Pencil優先）
  canvas.addEventListener('pointerdown', start, { passive: false });
  canvas.addEventListener('pointermove', move,  { passive: false });
  canvas.addEventListener('pointerup',   end);
  canvas.addEventListener('pointerleave',end);
  canvas.addEventListener('pointercancel',end);

  // タッチフォールバック
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

async function submitReceipt() {
  // 最低限チェック（宛名・金額は空でも提出可）
  const overlay = document.getElementById('loadingOverlay');
  overlay.style.display = 'flex';

  // 全フィールドのCanvasデータを収集
  const fields = {};
  FIELD_IDS.forEach(id => {
    const c = document.getElementById(id);
    if (!c) return;
    fields[id.replace('c_', '')] = isCanvasEmpty(c) ? '' : c.toDataURL('image/png');
  });

  try {
    const res = await fetch('/receipt/submit-handwriting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fields),
    });

    if (res.ok) {
      const data = await res.json();
      // 完了ページへ
      window.location.href = `/receipt/complete/${data.receipt_id}`;
    } else {
      overlay.style.display = 'none';
      const err = await res.text();
      alert('送信に失敗しました。\n' + err);
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
    // リサイズ時は描画内容を保存して再初期化
    FIELD_IDS.forEach(id => {
      const c = document.getElementById(id);
      if (!c) return;
      const img = c.toDataURL();
      initCanvas(c);
      if (img !== document.createElement('canvas').toDataURL()) {
        const image = new Image();
        const wrap  = c.parentElement;
        image.onload = () => {
          const ctx = c.getContext('2d');
          ctx.drawImage(image, 0, 0, wrap.clientWidth, wrap.clientHeight);
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

/* 受領書フォーム JS - 消費税計算 + 署名Canvas */

// ── 消費税自動計算 ──────────────────────────────────────────────────────────
function calcTax() {
  const rawVal = document.getElementById('amountInput').value.replace(/[,，¥\s]/g, '');
  const amount = parseFloat(rawVal);
  if (isNaN(amount) || amount <= 0) {
    document.getElementById('taxInput').value   = '';
    document.getElementById('totalInput').value = '';
    return;
  }
  const tax   = Math.floor(amount * 0.1);
  const total = amount + tax;
  document.getElementById('taxInput').value   = tax.toLocaleString();
  document.getElementById('totalInput').value = total.toLocaleString();
}

// ── 署名Canvas ─────────────────────────────────────────────────────────────
(function() {
  const canvas = document.getElementById('sigCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let drawing = false;
  let lastX = 0, lastY = 0;

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const dpr  = window.devicePixelRatio || 1;
    // 既存の描画を保存してリサイズ後に復元
    const img = canvas.toDataURL();
    canvas.width  = rect.width  * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    ctx.strokeStyle = '#1A237E';
    ctx.lineWidth   = 2.5;
    ctx.lineCap     = 'round';
    ctx.lineJoin    = 'round';
    // 画像復元
    const image = new Image();
    image.onload = () => ctx.drawImage(image, 0, 0, rect.width, rect.height);
    image.src = img;
  }

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const src  = e.touches ? e.touches[0] : e;
    return { x: src.clientX - rect.left, y: src.clientY - rect.top };
  }

  function startDraw(e) {
    // Apple Pencil (pointerType === 'pen') or touch or mouse
    drawing = true;
    const { x, y } = getPos(e);
    lastX = x; lastY = y;
    ctx.beginPath();
    ctx.moveTo(x, y);
    e.preventDefault();
  }

  function draw(e) {
    if (!drawing) return;
    e.preventDefault();
    const { x, y } = getPos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
    lastX = x; lastY = y;
  }

  function endDraw(e) {
    drawing = false;
    ctx.beginPath();
  }

  // Pointer Events API（Apple Pencil対応）
  canvas.addEventListener('pointerdown', startDraw, { passive: false });
  canvas.addEventListener('pointermove', draw,      { passive: false });
  canvas.addEventListener('pointerup',   endDraw);
  canvas.addEventListener('pointerleave',endDraw);

  // タッチフォールバック
  canvas.addEventListener('touchstart', startDraw, { passive: false });
  canvas.addEventListener('touchmove',  draw,      { passive: false });
  canvas.addEventListener('touchend',   endDraw);

  resize();
  window.addEventListener('resize', resize);
})();

// ── 署名消去 ───────────────────────────────────────────────────────────────
function clearSig() {
  const canvas = document.getElementById('sigCanvas');
  const ctx    = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}

// ── 送信前に署名DataURLをhiddenフィールドへセット ──────────────────────────
function prepareSubmit() {
  const canvas = document.getElementById('sigCanvas');
  // 何も描かれていない場合は空文字
  const blank  = document.createElement('canvas');
  blank.width  = canvas.width;
  blank.height = canvas.height;
  const isBlank = canvas.toDataURL() === blank.toDataURL();

  document.getElementById('signatureData').value = isBlank ? '' : canvas.toDataURL('image/png');

  // 店舗名を宛名フィールドに同期（両方の input が name=shop_name なので2つ目を name=shop_name2 にしている）
  const shop2 = document.querySelector('[name=shop_name2]');
  if (shop2) {
    const shop1 = document.querySelector('[name=shop_name]');
    if (shop1 && !shop1.value && shop2.value) shop1.value = shop2.value;
  }
  return true;
}

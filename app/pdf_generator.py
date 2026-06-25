"""受領書PDF生成 - 手書きCanvas画像を各フィールドに合成"""
import os, base64, io
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import ImageReader

# ── フォント ───────────────────────────────────────────────────────────────────
_BASE      = os.path.dirname(os.path.abspath(__file__))
_FONT_REG  = os.path.join(_BASE, "static", "fonts", "ipaexg.ttf")
_FONT_BOLD = os.path.join(_BASE, "static", "fonts", "ZenKakuGothicNew-Bold.ttf")
_fonts_ok  = False

def _ensure_fonts():
    global _fonts_ok
    if _fonts_ok: return
    pdfmetrics.registerFont(TTFont("JR", _FONT_REG))
    pdfmetrics.registerFont(TTFont("JB", _FONT_BOLD))
    _fonts_ok = True

FR, FB = "JR", "JB"

# ── 色 ────────────────────────────────────────────────────────────────────────
C_HDR   = HexColor("#3F51B5")
C_SEC   = HexColor("#5C6BC0")
C_SEC2  = HexColor("#607D8B")
C_LBL   = HexColor("#E8EAF6")
C_LBL_S = HexColor("#ECEFF1")
C_INP   = HexColor("#FFFDE7")
C_INP_S = HexColor("#FFFEF5")
C_GRAY  = HexColor("#F5F5F5")
C_TOT_V = HexColor("#EDE7F6")
C_STAMP = HexColor("#FFF3E0")
C_MID   = HexColor("#888888")
C_NOTE  = HexColor("#999999")


def _draw_field_image(cv, b64: str, x: float, y: float, w: float, h: float):
    """Canvas画像（dataURL）をPDF座標系に描画する"""
    if not b64 or not b64.startswith("data:image"):
        return
    try:
        raw = base64.b64decode(b64.split(",", 1)[1])
        img = ImageReader(io.BytesIO(raw))
        pad = 3
        cv.drawImage(img, x+pad, y+pad, width=w-pad*2, height=h-pad*2,
                     preserveAspectRatio=True, anchor="w", mask="auto")
    except Exception:
        pass


def _draw_field_value(cv, val: str, x: float, y: float, w: float, h: float, font="JR", fs=10):
    """画像またはテキストを描画する（どちらも対応）"""
    if not val:
        return
    if val.startswith("data:image"):
        _draw_field_image(cv, val, x, y, w, h)
    else:
        cv.saveState()
        cv.setFont(font, fs)
        cv.setFillColor(black)
        cv.drawString(x + 6, y + h / 2 - fs * 0.38, str(val))
        cv.restoreState()


def generate_receipt_pdf(data: dict, out_path: str) -> str:
    """
    data キー:
      fields: { atena, date, invoice, shopname, alias, realname,
                addr1, addr2, amount, tax, total, desc, sig }  ← Canvas base64 PNG
      store_name, store_address, store_contact, store_invoice_no
    """
    _ensure_fonts()

    W, H = A4
    MX   = 30
    CW   = W - MX * 2

    raw      = data.get("fields", {})
    # フィールド名を正規化（JSが送るキー名をPDFのキー名に統一）
    fields = {
        "atena":    raw.get("atena",    data.get("store_name", "")),
        "date":     raw.get("date",     ""),
        "invoice":  raw.get("invoice",  data.get("store_invoice_no", "")),
        "shopname": raw.get("shopname", data.get("store_name", "")),
        "alias":     raw.get("alias",     ""),
        "workplace": raw.get("workplace", data.get("workplace", "")),
        "realname":  raw.get("realname",  ""),
        "addr1":     raw.get("addr1",     raw.get("address", "")),
        "addr2":    raw.get("addr2",    ""),
        "amount":   raw.get("amount",   ""),
        "tax":      raw.get("tax",      ""),
        "total":    raw.get("total",    ""),
        "desc":     raw.get("desc",     ""),
        "sig":      raw.get("sig",      ""),
    }
    tmp_path = out_path + ".base.pdf"
    cv       = rl_canvas.Canvas(tmp_path, pagesize=A4)
    cv.setTitle("受領書")

    # ── ユーティリティ ─────────────────────────────────────────────────────────
    def fr(x, y, w, h, fill, stroke=black, lw=0.5):
        cv.saveState()
        cv.setLineWidth(lw); cv.setStrokeColor(stroke); cv.setFillColor(fill)
        cv.rect(x, y, w, h, fill=1, stroke=1)
        cv.restoreState()

    def t(x, y, s, font=FR, fs=9, color=black, align="left"):
        if not s: return
        cv.saveState()
        cv.setFont(font, fs); cv.setFillColor(color)
        if   align == "center": cv.drawCentredString(x, y, str(s))
        elif align == "right":  cv.drawRightString(x, y, str(s))
        else:                   cv.drawString(x, y, str(s))
        cv.restoreState()

    def sec(x, y, w, h, label, color=C_SEC):
        fr(x, y, w, h, color, black, 0.5)
        t(x+8, y+h/2-4, label, FB, 8, white)
        return y

    # 行描画: ラベル列＋手書き画像列
    LBL_W = 75   # ラベル列幅（固定pt）

    def row(x, y, w, h, label, field_key,
            lf=C_LBL, vf=C_INP, lf_fs=8, lw=0.5,
            prefix="", suffix="", prefix_w=0):
        # ラベル
        fr(x, y, LBL_W, h, lf, black, lw)
        t(x+LBL_W/2, y+h/2-lf_fs*0.4, label, FB, lf_fs, black if lf not in (C_HDR,) else white, "center")
        # プレフィックス（¥ or T）
        px = x + LBL_W
        if prefix:
            fr(px, y, prefix_w, h, vf, black, lw)
            t(px+prefix_w/2, y+h/2-9*0.4, prefix, FB, 11, black, "center")
            px += prefix_w
        # 入力エリア（手書き画像またはテキスト）
        vw = w - (px - x)
        fr(px, y, vw, h, vf, black, lw)
        _draw_field_value(cv, fields.get(field_key,""), px, y, vw, h, font=FR, fs=10)
        # サフィックス
        if suffix:
            t(x+w-14, y+h/2-9*0.4, suffix, FB, 12, black)
        return px, y, vw, h   # 値エリア座標

    # ── 外枠 ───────────────────────────────────────────────────────────────────
    OT, OB = H - 24, 58
    cv.saveState()
    cv.setLineWidth(2.5); cv.setStrokeColor(black)
    cv.rect(MX, OB, CW, OT-OB, fill=0, stroke=1)
    cv.restoreState()

    # ── タイトル ────────────────────────────────────────────────────────────────
    TH = 44; TY = OT - TH
    fr(MX, TY, CW, TH, C_HDR, black, 2.5)
    t(MX+CW/2, TY+TH/2-10, "受　　領　　書", FB, 20, white, "center")
    cur = TY

    # ── 宛名（大きめ） ──────────────────────────────────────────────────────────
    AH = 56; ALW = 60; SAMA_W = 28
    cur -= AH
    fr(MX,             cur, ALW,          AH, C_HDR, black, 1.5)
    t(MX+ALW/2,        cur+AH/2-7, "宛　名", FB, 11, white, "center")
    fr(MX+ALW,         cur, CW-ALW-SAMA_W, AH, C_INP, black, 1.5)
    _draw_field_value(cv, fields.get("atena",""), MX+ALW, cur, CW-ALW-SAMA_W, AH, font=FB, fs=14)
    fr(MX+CW-SAMA_W,   cur, SAMA_W, AH, C_INP, black, 1.5)
    t(MX+CW-SAMA_W/2,  cur+AH/2-8, "様", FB, 13, black, "center")

    SH = 15   # セクション見出し高さ
    RH = 44   # 通常行高

    # ── 受取人情報 ──────────────────────────────────────────────────────────────
    cur = sec(MX, cur-SH, CW, SH, "■ 受取人情報")
    cur -= RH; row(MX, cur, CW, RH, "キャスト名", "alias")
    cur -= RH; row(MX, cur, CW, RH, "本　　名", "realname")
    cur -= RH; row(MX, cur, CW, RH, "住　　所", "addr1")
    RA = 36   # 続き行
    cur -= RA; row(MX, cur, CW, RA, "（続き）", "addr2", lf=C_LBL_S, vf=C_INP_S, lf_fs=7)

    # ── 金額 ────────────────────────────────────────────────────────────────────
    cur = sec(MX, cur-SH, CW, SH, "■ 金額")

    RLG = 52  # 金額大きい行
    cur -= RLG
    fr(MX,        cur, LBL_W, RLG, C_LBL, black, 1.2)
    t(MX+LBL_W/2, cur+RLG/2-6, "金　　額", FB, 10, black, "center")
    PREW = 20
    fr(MX+LBL_W,  cur, PREW, RLG, C_INP, black, 1.2)
    t(MX+LBL_W+PREW/2, cur+RLG/2-8, "¥", FB, 13, black, "center")
    vx = MX+LBL_W+PREW; vw = CW-LBL_W-PREW
    fr(vx, cur, vw, RLG, C_INP, black, 1.2)
    _draw_field_value(cv, fields.get("amount",""), vx, cur, vw, RLG, font=FB, fs=16)

    # 消費税率固定
    RS = 34
    cur -= RS
    fr(MX,       cur, LBL_W, RS, C_GRAY, black, 0.5)
    t(MX+LBL_W/2,cur+RS/2-4, "消費税率", FR, 8, HexColor("#555555"), "center")
    fr(MX+LBL_W, cur, CW-LBL_W, RS, C_GRAY, black, 0.5)
    t(MX+LBL_W+8,cur+RS/2-4, "10%（固定）", FR, 8, HexColor("#555555"))

    # 消費税額
    cur -= RH; row(MX, cur, CW, RH, "消費税額", "tax", prefix="¥", prefix_w=PREW)

    # 合計金額
    cur -= RLG
    fr(MX,        cur, LBL_W, RLG, C_HDR, black, 1.5)
    t(MX+LBL_W/2, cur+RLG/2-6, "合計金額", FB, 10, white, "center")
    fr(MX+LBL_W,  cur, PREW, RLG, C_TOT_V, black, 1.5)
    t(MX+LBL_W+PREW/2, cur+RLG/2-9, "¥", FB, 14, C_HDR, "center")
    fr(MX+LBL_W+PREW, cur, CW-LBL_W-PREW, RLG, C_TOT_V, black, 1.5)
    _draw_field_value(cv, fields.get("total",""), MX+LBL_W+PREW, cur, CW-LBL_W-PREW, RLG, font=FB, fs=16)

    # ── 但し書 ──────────────────────────────────────────────────────────────────
    cur = sec(MX, cur-SH, CW, SH, "■ 但し書")
    RD = 48
    cur -= RD; row(MX, cur, CW, RD, "但 し 書", "desc")

    # ── 発行者情報 ──────────────────────────────────────────────────────────────
    cur = sec(MX, cur-SH, CW, SH, "■ 発行者情報", C_SEC2)
    STAMP_W = 60; INFO_W = CW - STAMP_W
    iss_top = cur
    iss_rows = [
        ("会 社 名", data.get("store_name",    "")),
        ("住　　所", data.get("store_address", "")),
        ("連 絡 先", data.get("store_contact", "")),
    ]
    if data.get("store_invoice_no"):
        iss_rows.append(("インボイス", "T" + data["store_invoice_no"]))
    IRH = 30
    for label, val in iss_rows:
        cur -= IRH
        fr(MX,         cur, LBL_W, IRH, C_LBL_S, black, 0.5)
        t(MX+LBL_W/2,  cur+IRH/2-4, label, FB, 7.5, black, "center")
        fr(MX+LBL_W,   cur, INFO_W-LBL_W, IRH, C_INP_S, black, 0.5)
        t(MX+LBL_W+6,  cur+IRH/2-4, val, FR, 8, black)
    stamp_h = iss_top - cur
    fr(MX+INFO_W, cur, STAMP_W, stamp_h, C_STAMP, black, 1)
    t(MX+INFO_W+STAMP_W/2, cur+stamp_h/2+4,  "㊞",   FR, 18, C_MID, "center")
    t(MX+INFO_W+STAMP_W/2, cur+stamp_h/2-14, "押印欄", FR, 7, C_MID, "center")

    # ── 署名欄 ──────────────────────────────────────────────────────────────────
    cur = sec(MX, cur-SH, CW, SH, "■ 署名欄")
    SIG_H = 60
    cur -= SIG_H
    sig_lw = LBL_W
    fr(MX,         cur, sig_lw,    SIG_H, C_HDR, black, 1.5)
    t(MX+sig_lw/2, cur+SIG_H/2-5, "署　名", FB, 9, white, "center")
    fr(MX+sig_lw,  cur, CW-sig_lw, SIG_H, C_INP, black, 1.5)
    _draw_field_value(cv, fields.get("sig",""), MX+sig_lw, cur, CW-sig_lw, SIG_H)

    t(MX, OB - 14, "※ 消費税率10%は固定　／　本書は受領の証として発行します", FR, 6.5, C_NOTE)

    cv.showPage()
    cv.save()

    import shutil
    shutil.copy(tmp_path, out_path)
    os.remove(tmp_path)
    return out_path

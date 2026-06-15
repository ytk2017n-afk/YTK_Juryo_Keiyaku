"""受領書PDF生成 - 新レイアウト（手書き3箇所、その他テキスト入力）"""
import os, base64, io
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject, DecodedStreamObject, DictionaryObject,
    FloatObject, NameObject, NumberObject, TextStringObject,
)

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


def _draw_field_image(cv, b64: str, x, y, w, h):
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


def generate_receipt_pdf(data: dict, out_path: str) -> str:
    """
    data キー:
      fields: { realname, alias, sig }  ← Canvas base64 PNG（手書き3箇所）
      date_text, atena, address, phone
      amount_text, tax_text, total_text, desc
      store_name, store_address, store_contact, store_invoice_no
    """
    _ensure_fonts()

    W, H = A4
    MX   = 30
    CW   = W - MX * 2

    fields = data.get("fields", {})

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
        return y - h

    LBL_W = 75   # ラベル列幅

    def text_row(x, y, w, h, label, value, lf=C_LBL, vf=C_INP, fs=8.5):
        """テキスト値を表示する行"""
        fr(x,         y, LBL_W, h, lf, black, 0.5)
        t(x+LBL_W/2,  y+h/2-4, label, FB, 7.5, black, "center")
        fr(x+LBL_W,   y, w-LBL_W, h, vf, black, 0.5)
        t(x+LBL_W+6,  y+h/2-4, value or "", FR, fs, black)

    def canvas_row(x, y, w, h, label, field_key, lf=C_LBL, vf=C_INP):
        """手書きCanvas画像を表示する行"""
        fr(x,        y, LBL_W, h, lf, black, 0.5)
        t(x+LBL_W/2, y+h/2-4, label, FB, 7.5, black, "center")
        vw = w - LBL_W
        fr(x+LBL_W,  y, vw, h, vf, black, 0.5)
        _draw_field_image(cv, fields.get(field_key, ""), x+LBL_W, y, vw, h)
        return x+LBL_W, y, vw, h

    def yen_text_row(x, y, w, h, label, value, lf=C_LBL, vf=C_INP, fs=11,
                     lf_color=black, lf_font=FB, lf_text_color=black):
        """¥プレフィックス付きテキスト行"""
        fr(x,        y, LBL_W, h, lf, black, 0.5)
        t(x+LBL_W/2, y+h/2-4, label, lf_font, 7.5, lf_text_color, "center")
        PREW = 18
        fr(x+LBL_W,       y, PREW, h, vf, black, 0.5)
        t(x+LBL_W+PREW/2, y+h/2-5, "¥", FB, 11, lf_color, "center")
        fr(x+LBL_W+PREW,  y, w-LBL_W-PREW, h, vf, black, 0.5)
        t(x+LBL_W+PREW+6, y+h/2-4, value or "", FR, fs, black)

    # ── 外枠 ───────────────────────────────────────────────────────────────────
    OT, OB = H - 24, 58
    cv.saveState()
    cv.setLineWidth(2.5); cv.setStrokeColor(black)
    cv.rect(MX, OB, CW, OT-OB, fill=0, stroke=1)
    cv.restoreState()

    # ── タイトル ────────────────────────────────────────────────────────────────
    TH = 40; TY = OT - TH
    fr(MX, TY, CW, TH, C_HDR, black, 2.5)
    t(MX+CW/2, TY+TH/2-9, "受　　領　　書", FB, 18, white, "center")
    cur = TY

    # ── 日付 ────────────────────────────────────────────────────────────────────
    DH = 28
    cur -= DH
    text_row(MX, cur, CW, DH, "日　　付", data.get("date_text", ""), lf=C_LBL, vf=C_INP)

    # ── 宛名 ────────────────────────────────────────────────────────────────────
    AH = 44
    cur -= AH
    ALW = 55; SAMA_W = 30
    fr(MX,           cur, ALW,              AH, C_HDR, black, 1.5)
    t(MX+ALW/2,      cur+AH/2-7, "宛　名", FB, 11, white, "center")
    fr(MX+ALW,       cur, CW-ALW-SAMA_W,   AH, C_INP, black, 1.5)
    atena = data.get("atena", "")
    t(MX+ALW+8,      cur+AH/2-7, atena, FB, 13, black)
    fr(MX+CW-SAMA_W, cur, SAMA_W,           AH, C_INP, black, 1.5)
    t(MX+CW-SAMA_W/2,cur+AH/2-7, "様", FB, 13, black, "center")

    SH = 12   # セクション見出し高さ
    RH = 36   # 通常行高

    # ── 受取人情報 ──────────────────────────────────────────────────────────────
    cur = sec(MX, cur-SH, CW, SH, "■ 受取人情報")
    cur -= RH+4; canvas_row(MX, cur, CW, RH+4, "本　　名", "realname")
    cur -= RH;   text_row(MX, cur, CW, RH, "源 氏 名", data.get("alias", ""))
    cur -= RH;   text_row(MX, cur, CW, RH, "住　　所",  data.get("address", ""))
    cur -= RH;   text_row(MX, cur, CW, RH, "電話番号",  data.get("phone",   ""))

    # ── 金額 ────────────────────────────────────────────────────────────────────
    cur = sec(MX, cur-SH, CW, SH, "■ 金額")

    RLG = 42
    cur -= RLG
    fr(MX,        cur, LBL_W, RLG, C_LBL, black, 1.2)
    t(MX+LBL_W/2, cur+RLG/2-5, "金　　額", FB, 9, black, "center")
    PREW = 18
    fr(MX+LBL_W,  cur, PREW, RLG, C_INP, black, 1.2)
    t(MX+LBL_W+PREW/2, cur+RLG/2-7, "¥", FB, 12, black, "center")
    vx = MX+LBL_W+PREW; vw = CW-LBL_W-PREW
    fr(vx, cur, vw, RLG, C_INP, black, 1.2)
    t(vx+6, cur+RLG/2-5, data.get("amount_text", ""), FR, 11, black)

    # 消費税率固定
    RS = 26
    cur -= RS
    fr(MX,       cur, LBL_W, RS, C_GRAY, black, 0.5)
    t(MX+LBL_W/2,cur+RS/2-4, "消費税率", FR, 7.5, HexColor("#555555"), "center")
    fr(MX+LBL_W, cur, CW-LBL_W, RS, C_GRAY, black, 0.5)
    t(MX+LBL_W+8,cur+RS/2-4, "10%（固定）", FR, 8, HexColor("#555555"))

    # 消費税額
    cur -= RH
    text_row(MX, cur, CW, RH, "消費税額", "", lf=C_LBL, vf=C_INP)
    fr(MX+LBL_W,       cur, PREW, RH, C_INP, black, 0.5)
    t(MX+LBL_W+PREW/2, cur+RH/2-4, "¥", FB, 10, black, "center")
    fr(MX+LBL_W+PREW,  cur, CW-LBL_W-PREW, RH, C_INP, black, 0.5)
    t(MX+LBL_W+PREW+6, cur+RH/2-4, data.get("tax_text", ""), FR, 9, black)

    # 合計金額
    cur -= RLG
    fr(MX,        cur, LBL_W, RLG, C_HDR, black, 1.5)
    t(MX+LBL_W/2, cur+RLG/2-5, "合計金額", FB, 9, white, "center")
    fr(MX+LBL_W,  cur, PREW, RLG, C_TOT_V, black, 1.5)
    t(MX+LBL_W+PREW/2, cur+RLG/2-8, "¥", FB, 13, C_HDR, "center")
    fr(MX+LBL_W+PREW, cur, CW-LBL_W-PREW, RLG, C_TOT_V, black, 1.5)
    t(MX+LBL_W+PREW+6, cur+RLG/2-5, data.get("total_text", ""), FB, 11, C_HDR)

    # ── 但し書 ──────────────────────────────────────────────────────────────────
    cur = sec(MX, cur-SH, CW, SH, "■ 但し書")
    RD = 32
    cur -= RD
    text_row(MX, cur, CW, RD, "但 し 書", data.get("desc", ""))

    # ── 発行者情報 ──────────────────────────────────────────────────────────────
    cur = sec(MX, cur-SH, CW, SH, "■ 発行者情報", C_SEC2)
    STAMP_W = 55; INFO_W = CW - STAMP_W
    iss_top = cur
    iss_rows = [
        ("会 社 名", data.get("store_name",    "")),
        ("住　　所", data.get("store_address", "")),
        ("連 絡 先", data.get("store_contact", "")),
    ]
    if data.get("store_invoice_no"):
        iss_rows.append(("インボイス", "T" + data["store_invoice_no"]))
    IRH = 22
    for label, val in iss_rows:
        cur -= IRH
        fr(MX,         cur, LBL_W, IRH, C_LBL_S, black, 0.5)
        t(MX+LBL_W/2,  cur+IRH/2-4, label, FB, 7, black, "center")
        fr(MX+LBL_W,   cur, INFO_W-LBL_W, IRH, C_INP_S, black, 0.5)
        t(MX+LBL_W+6,  cur+IRH/2-4, val, FR, 7.5, black)
    stamp_h = iss_top - cur
    fr(MX+INFO_W, cur, STAMP_W, stamp_h, C_STAMP, black, 1)
    t(MX+INFO_W+STAMP_W/2, cur+stamp_h/2+4,  "㊞",   FR, 16, C_MID, "center")
    t(MX+INFO_W+STAMP_W/2, cur+stamp_h/2-12, "押印欄", FR, 7, C_MID, "center")

    # ── 署名欄 ──────────────────────────────────────────────────────────────────
    SIG_H = 44; SIG_Y = OB + 2
    sig_lw = LBL_W
    fr(MX,         SIG_Y, sig_lw,     SIG_H, C_HDR, black, 1.5)
    t(MX+sig_lw/2, SIG_Y+SIG_H/2-5,  "署　名", FB, 9, white, "center")
    fr(MX+sig_lw,  SIG_Y, CW-sig_lw, SIG_H, C_INP, black, 1.5)
    _draw_field_image(cv, fields.get("sig", ""), MX+sig_lw, SIG_Y, CW-sig_lw, SIG_H)

    SFX, SFY, SFW, SFH = MX+sig_lw, SIG_Y, CW-sig_lw, SIG_H

    t(MX, 10, "※ 消費税率10%は固定　／　本書は受領の証として発行します", FR, 6.5, C_NOTE)

    cv.showPage()
    cv.save()

    # ── AcroForm 署名フィールド追加 ────────────────────────────────────────────
    reader = PdfReader(tmp_path)
    writer = PdfWriter()
    writer.append(reader)
    page = writer.pages[0]

    ap_n = DecodedStreamObject()
    ap_n.set_data(b"")
    ap_n.update({
        NameObject("/Type"):    NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Form"),
        NameObject("/BBox"):    ArrayObject([FloatObject(0), FloatObject(0), FloatObject(SFW), FloatObject(SFH)]),
    })
    sig = DictionaryObject({
        NameObject("/Type"):    NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Widget"),
        NameObject("/FT"):      NameObject("/Sig"),
        NameObject("/T"):       TextStringObject("signature"),
        NameObject("/TU"):      TextStringObject("署名欄"),
        NameObject("/F"):       NumberObject(4),
        NameObject("/Rect"):    ArrayObject([FloatObject(SFX), FloatObject(SFY), FloatObject(SFX+SFW), FloatObject(SFY+SFH)]),
        NameObject("/AP"):      DictionaryObject({NameObject("/N"): writer._add_object(ap_n)}),
    })
    sig_ref = writer._add_object(sig)
    if "/Annots" not in page:
        page[NameObject("/Annots")] = ArrayObject()
    page[NameObject("/Annots")].append(sig_ref)
    writer._root_object[NameObject("/AcroForm")] = DictionaryObject({
        NameObject("/Fields"):   ArrayObject([sig_ref]),
        NameObject("/SigFlags"): NumberObject(3),
    })

    with open(out_path, "wb") as f:
        writer.write(f)

    os.remove(tmp_path)
    return out_path

"""業務委託契約書PDF生成 - 手書きCanvas画像を乙の各フィールドに合成"""
import os, base64, io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Flowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.utils import ImageReader

# ── フォント ──────────────────────────────────────────────────────────────────
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
C_HDR  = HexColor("#3F51B5")
C_LBL  = HexColor("#E8EAF6")
C_INP  = HexColor("#FFFDE7")
C_AUTO = HexColor("#EEF2FF")   # 甲（自動入力）
C_NOTE = HexColor("#999999")

LBL_W = 22 * mm   # ラベル列幅（Flowable共通）


# ── 手書きフィールド（乙） ─────────────────────────────────────────────────────
class HandwritingField(Flowable):
    def __init__(self, b64, label, height=14*mm):
        Flowable.__init__(self)
        self.b64    = b64
        self.label  = label
        self.height = height

    def wrap(self, availWidth, availHeight):
        self.w = availWidth
        return (self.w, self.height)

    def draw(self):
        c = self.canv
        lw, h, vw = LBL_W, self.height, self.w - LBL_W

        # ラベル
        c.saveState()
        c.setFillColor(C_LBL); c.setStrokeColor(black); c.setLineWidth(0.5)
        c.rect(0, 0, lw, h, fill=1, stroke=1)
        c.setFillColor(black); c.setFont(FB, 7.5)
        c.drawCentredString(lw/2, h/2 - 3.5, self.label)

        # 入力欄（手書き）
        c.setFillColor(C_INP)
        c.rect(lw, 0, vw, h, fill=1, stroke=1)
        if self.b64 and self.b64.startswith("data:image"):
            try:
                raw = base64.b64decode(self.b64.split(",", 1)[1])
                img = ImageReader(io.BytesIO(raw))
                pad = 2
                c.drawImage(img, lw+pad, pad, width=vw-pad*2, height=h-pad*2,
                            preserveAspectRatio=True, anchor="w", mask="auto")
            except Exception:
                pass
        c.restoreState()


# ── 自動入力フィールド（甲） ──────────────────────────────────────────────────
class AutoField(Flowable):
    def __init__(self, text, label, height=11*mm):
        Flowable.__init__(self)
        self.text   = text
        self.label  = label
        self.height = height

    def wrap(self, availWidth, availHeight):
        self.w = availWidth
        return (self.w, self.height)

    def draw(self):
        c = self.canv
        lw, h, vw = LBL_W, self.height, self.w - LBL_W

        c.saveState()
        c.setFillColor(C_LBL); c.setStrokeColor(black); c.setLineWidth(0.5)
        c.rect(0, 0, lw, h, fill=1, stroke=1)
        c.setFillColor(black); c.setFont(FB, 7.5)
        c.drawCentredString(lw/2, h/2 - 3.5, self.label)

        c.setFillColor(C_AUTO)
        c.rect(lw, 0, vw, h, fill=1, stroke=1)
        c.setFillColor(black); c.setFont(FR, 8.5)
        c.drawString(lw + 4*mm, h/2 - 3.5, self.text or "")
        c.restoreState()


# ── セクション見出し ───────────────────────────────────────────────────────────
class SectionBar(Flowable):
    def __init__(self, label, height=7*mm):
        Flowable.__init__(self)
        self.label  = label
        self.height = height

    def wrap(self, availWidth, availHeight):
        self.w = availWidth
        return (self.w, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(C_HDR); c.setStrokeColor(black); c.setLineWidth(0.5)
        c.rect(0, 0, self.w, self.height, fill=1, stroke=1)
        c.setFillColor(white); c.setFont(FB, 8)
        c.drawString(3*mm, self.height/2 - 3, self.label)
        c.restoreState()


# ── メイン生成関数 ─────────────────────────────────────────────────────────────
def generate_contract_pdf(data: dict, out_path: str) -> str:
    """
    data キー:
      fields: { oto_preamble, oto_realname }  ← Canvas base64 PNG（手書き2箇所）
      date_text, oto_addr, oto_alias          ← テキスト入力
      store_name, store_address
    """
    _ensure_fonts()

    fields        = data.get("fields", {})
    store_name    = data.get("store_name",    "")
    store_address = data.get("store_address", "")
    date_text     = data.get("date_text",     "")
    oto_addr      = data.get("oto_addr",      "")
    oto_alias     = data.get("oto_alias",     "")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=25*mm, rightMargin=25*mm,
        topMargin=20*mm,  bottomMargin=20*mm,
        title="業務委託契約書",
    )

    def sty(name, **kw):
        d = dict(fontName=FR, fontSize=8.5, leading=15)
        d.update(kw)
        return ParagraphStyle(name, **d)

    T  = sty("t",  fontName=FB, fontSize=15, alignment=TA_CENTER, spaceAfter=8*mm)
    P  = sty("p",  alignment=TA_JUSTIFY, spaceAfter=1*mm)
    AB = sty("ab", fontName=FB, fontSize=8.5, spaceBefore=5*mm, spaceAfter=1*mm)
    IT = sty("it", alignment=TA_JUSTIFY, leftIndent=6*mm)
    CL = sty("cl", alignment=TA_JUSTIFY, spaceBefore=6*mm, spaceAfter=3*mm)
    SL = sty("sl", fontName=FB, fontSize=8.5, spaceBefore=2*mm, spaceAfter=1*mm)

    SP = lambda n=2: Spacer(1, n*mm)

    story = []

    # ── タイトル ────────────────────────────────────────────────────────────────
    story.append(Paragraph("業　務　委　託　契　約　書", T))

    # ── 前文 ─────────────────────────────────────────────────────────────────
    story.append(SectionBar("■ 甲（委託者）"))
    story.append(SP(1))
    story.append(AutoField(store_name,    "店　舗　名"))
    story.append(SP(1))
    story.append(AutoField(store_address, "住　　　所"))
    story.append(SP(3))

    story.append(SectionBar("■ 乙（受託者）"))
    story.append(SP(1))
    story.append(HandwritingField(fields.get("oto_preamble",""), "氏　　　名", height=13*mm))
    story.append(SP(3))

    story.append(Paragraph(
        "上記の甲（以下「甲」という。）と、上記の乙（以下「乙」という。）とは、"
        "甲の事業である飲食等営業の業務の一部を乙に委託するものとし、"
        "ここに業務委託契約（以下「本契約」という。）を締結する。",
        P
    ))

    # ── 条文 ────────────────────────────────────────────────────────────────
    articles = [
        ("第１条（契約業務の内容）", [
            "甲、乙共に法令を厳守し、甲は乙に対し本契約における業務内容を詳細に説明し乙はこれを遵守すること。",
        ]),
        ("第２条（契約期間）", [
            "１．本契約の有効期間は、契約締結の日から36ヶ月とする。",
            "２．本契約には更新の定めはなく、契約期間満了後に改めて契約する場合は甲乙協議の上、再度契約を締結する。なお契約は書面契約、口頭契約を問わない。",
        ]),
        ("第３条（業務委託の遂行方法）", [
            "１．委託業務の遂行にあたって、稼動日及び稼働時間は乙の裁量に属するものとし許諾の自由を有するものとする。",
            "２．したがって勤務場所・時間についての指定・管理は行わないものとする。",
            "３．業務の内容及び遂行方法に対する指揮監督は受けないものとする。",
            "４．但し、業務遂行の必要性などから、事前の十分な打合せ等、関係者間で協議しつつ協力関係を保持することとする。",
        ]),
        ("第４条（委託手数料）", [
            "１．甲が乙に対し支払う本契約の委託手数料は、甲の業務委託手数料表に基づき、法令で定められた源泉所得税及び第7条に定める経費等の合計額を差し引いた金額を、甲が乙に対し現金による支払いを原則とする。",
            "　　なお、甲が乙に支払う業務委託手数料には消費税が含まれている。",
            "２．乙の公租については、乙自らの責任において対処すること。",
        ]),
        ("第５条（委託手数料率の改訂）", [
            "第４条に規定した委託手数料率は、物価・経済状況の変化、その他料率の変更を必要とする事由が生じた場合は、甲乙協議の上、委託手数料率を改訂することができる。",
        ]),
        ("第６条（本契約における乙の地位）", [
            "１．乙は、甲が委託する業務を請け負うものであり、甲との雇用関係にはなく、当然に社会保険・労働保険の加入はない。",
            "２．したがって、業務上の災害など万一の場合においても、雇用関係としての補償を甲に対して求めることはできないものとする。",
            "３．乙は自己の責任において、適切な確定申告を行い納税の義務を果たすものとする。",
            "４．乙は独立した個人事業主であるため甲は乙の兼業を禁止することはできない。",
        ]),
        ("第７条（業務委託に付随する経費等）", [
            "１．乙が委託業務を実施するために必要な着類、用具、ヘアメイク等に対しての経費、及び維持費は乙の負担とし、乙は自らの責任において着類等を調達し、ヘアメイクを行う。",
            "２．なお、乙が業務を遂行する際に必要となる用具、ヘアメイク等は甲から有料にて支給若しくは貸出を受けることもできる。",
        ]),
        ("第８条（損害賠償）", [
            "１．本契約業務の遂行中、乙の故意または過失により、甲もしくは第三者に与えた損害に対し、乙は損害賠償の責任を負う。",
            "２．甲の事業である接待飲食等営業の利用者がその業務に対して支払うべきサービスの利用料に関して未収が生じた場合には、乙が利用者から収受し、甲に受け渡すものとする。なお、乙が利用者から収受した利用料を甲に受け渡す前に紛失した場合又は乙が利用者から収受できなかった場合は、未収の額と同等の額を甲に支払わなければならない。",
        ]),
        ("第９条（禁止事項）", [
            "１．乙は、委託業務の遂行時間以外で待機の時間が生じた場合であっても、待機時間を甲の事務所において過ごすことはできない。",
            "２．ただし待機場所の使用料を支払うことで甲の事務所にて待機することができる。",
        ]),
        ("第10条（守秘義務）", [
            "乙は、本契約に基づき業務上知り得た情報、または甲の機密書類及びデータ等を外部に持ち出し、第三者に対し提供または漏洩してはならない。万一、違反した場合は甲に対し損害賠償の責を負う。",
        ]),
        ("第11条（所有権及び肖像権）", [
            "業務遂行にあたり必要となる写真、情報については甲に所有権があることとする。",
        ]),
        ("第12条（協議）", [
            "本契約書及び個別契約書に定めのない事項、または本契約及び個別契約の履行にあたり疑義を生じた事項は、甲乙協議の上円満に解決をはかるものとする。",
        ]),
    ]

    for title, items in articles:
        story.append(Paragraph(title, AB))
        for item in items:
            story.append(Paragraph(item, IT))

    # ── 末文 ────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        "本契約を締結したことを証するため本書を1通作成し、甲乙記名捺印の上、"
        "甲が原本を乙が写しを保有する。",
        CL
    ))

    # ── 署名欄 ──────────────────────────────────────────────────────────────
    story.append(AutoField(date_text, "日　　付", height=11*mm))
    story.append(SP(4))

    story.append(Paragraph("甲", sty("kos", fontName=FB, fontSize=8.5)))
    story.append(SP(1))
    story.append(AutoField(store_address, "住　　所", height=11*mm))
    story.append(SP(1))
    story.append(AutoField(store_name,    "名　　称", height=11*mm))
    story.append(SP(5))

    story.append(Paragraph("乙", sty("otos", fontName=FB, fontSize=8.5)))
    story.append(SP(1))
    story.append(AutoField(oto_addr,  "住　　所",    height=11*mm))
    story.append(SP(1))
    story.append(HandwritingField(fields.get("oto_realname", ""), "氏名（本名）", height=13*mm))
    story.append(SP(1))
    story.append(AutoField(oto_alias, "キャスト名",    height=11*mm))
    story.append(SP(1))
    story.append(HandwritingField(fields.get("oto_sig", ""), "署　　名", height=14*mm))

    story.append(SP(4))
    story.append(Paragraph("Ver.キャバクラ190522", sty("ver", fontSize=7, textColor=C_NOTE)))

    doc.build(story)
    return out_path

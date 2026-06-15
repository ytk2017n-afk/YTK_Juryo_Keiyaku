"""受領書Webアプリ - FastAPI メインモジュール"""
import os, io, zipfile, csv
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from database import get_db, init_db, Store, Receipt, Contract
from pdf_generator import generate_receipt_pdf
from contract_pdf_generator import generate_contract_pdf

# ── 初期化 ─────────────────────────────────────────────────────────────────────
init_db()

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.getenv("SECRET_KEY", "ytk-receipt-secret-change-in-prod-2024")


def _generate_pdf_bytes(generator_fn, data: dict) -> bytes:
    """PDFをメモリ上で生成してバイト列で返す"""
    tmp = io.BytesIO()
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        tmp_path = f.name
    try:
        generator_fn(data, tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            _os.remove(tmp_path)
        except Exception:
            pass

app = FastAPI(title="受領書管理システム")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates  = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
pwd_ctx    = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
serializer = URLSafeTimedSerializer(SECRET_KEY)

# ── セッション管理 ─────────────────────────────────────────────────────────────
SESSION_COOKIE = "ytk_session"
SESSION_MAX_AGE = 60 * 60 * 8   # 8時間

def create_session(store_id: int, is_admin: bool) -> str:
    return serializer.dumps({"id": store_id, "admin": is_admin})

def get_current_store(request: Request, db: Session = Depends(get_db)) -> Optional[Store]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return db.query(Store).filter(Store.id == data["id"], Store.is_active == True).first()
    except (BadSignature, SignatureExpired):
        return None

def require_login(request: Request, db: Session = Depends(get_db)) -> Store:
    store = get_current_store(request, db)
    if not store:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return store

def require_admin(request: Request, db: Session = Depends(get_db)) -> Store:
    store = require_login(request, db)
    if not store.is_admin:
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return store

# ── ログイン ───────────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
async def login(
    request: Request,
    login_id: str = Form(...),
    password:  str = Form(...),
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter(Store.login_id == login_id, Store.is_active == True).first()
    if not store or not pwd_ctx.verify(password, store.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "IDまたはパスワードが違います"},
            status_code=401,
        )
    token = create_session(store.id, store.is_admin)
    resp  = RedirectResponse(url="/admin" if store.is_admin else "/receipt", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return resp

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp

# ── 受領書フォーム（店舗スタッフ） ─────────────────────────────────────────────
@app.get("/receipt", response_class=HTMLResponse)
async def receipt_form(
    request: Request,
    store: Store = Depends(require_login),
):
    return templates.TemplateResponse("receipt_form.html", {
        "request":   request,
        "store":     store,
        "today_iso": datetime.now().strftime("%Y-%m-%d"),
    })

@app.post("/receipt/submit-handwriting")
async def submit_handwriting(
    request: Request,
    store: Store = Depends(require_login),
    db: Session = Depends(get_db),
):
    """手書きCanvasの画像データ（JSON）を受け取りPDFを生成"""
    fields = await request.json()   # { atena, date, invoice, shopname, alias, realname, addr1, addr2, amount, tax, total, desc, sig }

    receipt = Receipt(
        store_id      = store.id,
        shop_name     = store.store_name,
        receipt_date  = fields.get("date", ""),
        invoice_no    = store.invoice_no or "",
        name_alias    = "",   # 手書きのためテキスト取得不可
        name_real     = "",   # 手書きのためテキスト取得不可
        address       = fields.get("address", ""),
        amount        = fields.get("amount", ""),
        tax_amount    = fields.get("tax", ""),
        total_amount  = fields.get("total", ""),
        description   = fields.get("desc", ""),
        signature_b64 = fields.get("sig", ""),
    )
    db.add(receipt)
    db.flush()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"receipt_{store.login_id}_{receipt.id}_{timestamp}.pdf"

    pdf_bytes = _generate_pdf_bytes(generate_receipt_pdf, {
        "fields":          fields,          # realname/alias/sig の canvas base64
        "date_text":       fields.get("date", ""),
        "atena":           store.store_name,
        "address":         fields.get("address", ""),
        "phone":           fields.get("phone", ""),
        "amount_text":     fields.get("amount", ""),
        "tax_text":        fields.get("tax", ""),
        "total_text":      fields.get("total", ""),
        "desc":            fields.get("desc", ""),
        "store_name":      store.store_name,
        "store_address":   store.store_address or "",
        "store_contact":   store.store_contact or "",
        "store_invoice_no": store.invoice_no or "",
    })

    receipt.pdf_filename = filename
    receipt.pdf_data     = pdf_bytes
    db.commit()

    return JSONResponse({"receipt_id": receipt.id, "pdf_url": f"/receipt/pdf/{receipt.id}"})


@app.get("/receipt/complete/{receipt_id}", response_class=HTMLResponse)
async def receipt_complete(
    receipt_id: int,
    request: Request,
    store: Store = Depends(require_login),
    db: Session = Depends(get_db),
):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id, Receipt.store_id == store.id).first()
    if not receipt:
        raise HTTPException(404)
    return templates.TemplateResponse("receipt_complete.html", {
        "request": request,
        "store":   store,
        "receipt": receipt,
        "pdf_url": f"/receipt/pdf/{receipt.id}",
    })

@app.get("/receipt/pdf/{receipt_id}")
async def download_receipt_pdf(
    receipt_id: int,
    store: Store = Depends(require_login),
    db: Session = Depends(get_db),
):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(404, "受領書が見つかりません")
    # 管理者 or 自店舗のみ
    if not store.is_admin and receipt.store_id != store.id:
        raise HTTPException(403)
    if not receipt.pdf_data:
        raise HTTPException(404, "PDFデータが見つかりません")
    return StreamingResponse(
        io.BytesIO(receipt.pdf_data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{receipt.pdf_filename}"'},
    )

# ── 管理者ダッシュボード ────────────────────────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    store: Store = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total_receipts = db.query(Receipt).filter(Receipt.is_deleted == False).count()
    total_stores   = db.query(Store).filter(Store.is_admin == False, Store.is_active == True).count()
    recent = (db.query(Receipt)
               .filter(Receipt.is_deleted == False)
               .order_by(Receipt.submitted_at.desc())
               .limit(10).all())
    return templates.TemplateResponse("admin/dashboard.html", {
        "request":       request,
        "store":         store,
        "total_receipts": total_receipts,
        "total_stores":   total_stores,
        "recent":         recent,
    })

@app.get("/admin/receipts", response_class=HTMLResponse)
async def admin_receipts(
    request: Request,
    q:          str = "",
    store_id:   int = 0,
    date_from:  str = "",
    date_to:    str = "",
    page:       int = 1,
    store: Store = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Receipt).filter(Receipt.is_deleted == False)
    if store_id:
        query = query.filter(Receipt.store_id == store_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            Receipt.shop_name.like(like)  |
            Receipt.name_alias.like(like) |
            Receipt.name_real.like(like)
        )
    total  = query.count()
    limit  = 20
    offset = (page - 1) * limit
    receipts = query.order_by(Receipt.submitted_at.desc()).offset(offset).limit(limit).all()
    stores   = db.query(Store).filter(Store.is_admin == False).all()
    return templates.TemplateResponse("admin/receipts.html", {
        "request":  request,
        "store":    store,
        "receipts": receipts,
        "stores":   stores,
        "q":        q,
        "sel_store": store_id,
        "total":    total,
        "page":     page,
        "pages":    (total + limit - 1) // limit,
    })

@app.get("/admin/receipts/download-zip")
async def download_zip(
    store_id: int = 0,
    store: Store = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Receipt).filter(Receipt.is_deleted == False, Receipt.pdf_filename != None)
    if store_id:
        query = query.filter(Receipt.store_id == store_id)
    receipts = query.all()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in receipts:
            if r.pdf_data:
                zf.writestr(r.pdf_filename or f"receipt_{r.id}.pdf", r.pdf_data)
    buf.seek(0)
    fname = f"receipts_{datetime.now().strftime('%Y%m%d')}.zip"
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})

@app.get("/admin/receipts/export-csv")
async def export_csv(
    store_id: int = 0,
    store: Store = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Receipt).filter(Receipt.is_deleted == False)
    if store_id:
        query = query.filter(Receipt.store_id == store_id)
    receipts = query.order_by(Receipt.submitted_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID","店舗","日付","宛名(店舗名)","源氏名","本名","住所",
                     "金額","消費税額","合計金額","但し書","提出日時"])
    for r in receipts:
        writer.writerow([
            r.id, r.store.store_name if r.store else "",
            r.receipt_date, r.shop_name, r.name_alias, r.name_real,
            r.address, r.amount, r.tax_amount, r.total_amount,
            r.description,
            r.submitted_at.strftime("%Y-%m-%d %H:%M") if r.submitted_at else "",
        ])
    buf.seek(0)
    fname = f"receipts_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )

# ── 店舗マスタ管理 ─────────────────────────────────────────────────────────────
@app.get("/admin/stores", response_class=HTMLResponse)
async def admin_stores(
    request: Request,
    store: Store = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stores = db.query(Store).filter(Store.is_admin == False).order_by(Store.id).all()
    return templates.TemplateResponse("admin/stores.html", {
        "request": request,
        "store":   store,
        "stores":  stores,
    })

@app.post("/admin/stores/create")
async def create_store(
    request: Request,
    login_id:      str = Form(...),
    password:      str = Form(...),
    store_name:    str = Form(...),
    store_address: str = Form(""),
    store_contact: str = Form(""),
    invoice_no:    str = Form(""),
    store: Store = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(Store).filter(Store.login_id == login_id).first():
        raise HTTPException(400, "そのログインIDは既に使われています")
    new_store = Store(
        login_id       = login_id,
        password_hash  = pwd_ctx.hash(password),
        plain_password = password,
        store_name     = store_name,
        store_address  = store_address,
        store_contact  = store_contact,
        invoice_no     = invoice_no,
    )
    db.add(new_store)
    db.commit()
    return RedirectResponse("/admin/stores", status_code=303)

@app.post("/admin/stores/{store_id}/delete")
async def delete_store(
    store_id: int,
    store: Store = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(Store).filter(Store.id == store_id, Store.is_admin == False).first()
    if not target:
        raise HTTPException(404)
    db.delete(target)
    db.commit()
    return RedirectResponse("/admin/stores", status_code=303)

@app.post("/admin/stores/{store_id}/update")
async def update_store(
    store_id: int,
    login_id:      str = Form(...),
    store_name:    str = Form(...),
    store_address: str = Form(""),
    store_contact: str = Form(""),
    invoice_no:    str = Form(""),
    new_password:  str = Form(""),
    is_active:     str = Form("on"),
    store: Store = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(Store).filter(Store.id == store_id).first()
    if not target:
        raise HTTPException(404)
    # login_id変更時の重複チェック
    if login_id != target.login_id:
        if db.query(Store).filter(Store.login_id == login_id).first():
            raise HTTPException(400, "そのログインIDは既に使われています")
        target.login_id = login_id
    target.store_name    = store_name
    target.store_address = store_address
    target.store_contact = store_contact
    target.invoice_no    = invoice_no
    target.is_active     = (is_active == "on")
    if new_password:
        target.password_hash  = pwd_ctx.hash(new_password)
        target.plain_password = new_password
    db.commit()
    return RedirectResponse("/admin/stores", status_code=303)

# ── 契約書フォーム（店舗スタッフ） ─────────────────────────────────────────────
@app.get("/contract", response_class=HTMLResponse)
async def contract_form(
    request: Request,
    store: Store = Depends(require_login),
):
    return templates.TemplateResponse("contract_form.html", {
        "request": request,
        "store":   store,
        "today":   datetime.now().strftime("%Y年%m月%d日"),
    })


@app.post("/contract/submit")
async def submit_contract(
    request: Request,
    store: Store = Depends(require_login),
    db: Session = Depends(get_db),
):
    """手書きCanvasの画像データ（JSON）を受け取り契約書PDFを生成"""
    fields = await request.json()

    contract = Contract(
        store_id         = store.id,
        oto_preamble_b64 = fields.get("oto_preamble", ""),
        date_b64         = fields.get("date", ""),
        oto_addr_b64     = fields.get("oto_addr", ""),
        oto_realname_b64 = fields.get("oto_realname", ""),
        oto_alias_b64    = fields.get("oto_alias", ""),
    )
    db.add(contract)
    db.flush()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"contract_{store.login_id}_{contract.id}_{timestamp}.pdf"

    pdf_bytes = _generate_pdf_bytes(generate_contract_pdf, {
        "fields":        fields,
        "store_name":    store.store_name,
        "store_address": store.store_address or "",
    })

    contract.pdf_filename = filename
    contract.pdf_data     = pdf_bytes
    db.commit()

    return JSONResponse({"contract_id": contract.id, "pdf_url": f"/contract/pdf/{contract.id}"})


@app.get("/contract/complete/{contract_id}", response_class=HTMLResponse)
async def contract_complete(
    contract_id: int,
    request:     Request,
    store: Store = Depends(require_login),
    db: Session  = Depends(get_db),
):
    contract = db.query(Contract).filter(
        Contract.id == contract_id, Contract.store_id == store.id
    ).first()
    if not contract:
        raise HTTPException(404)
    return templates.TemplateResponse("contract_complete.html", {
        "request":  request,
        "store":    store,
        "contract": contract,
        "pdf_url":  f"/contract/pdf/{contract.id}",
    })


@app.get("/contract/pdf/{contract_id}")
async def download_contract_pdf(
    contract_id: int,
    store: Store = Depends(require_login),
    db: Session  = Depends(get_db),
):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(404, "契約書が見つかりません")
    if not store.is_admin and contract.store_id != store.id:
        raise HTTPException(403)
    if not contract.pdf_data:
        raise HTTPException(404, "PDFデータが見つかりません")
    return StreamingResponse(
        io.BytesIO(contract.pdf_data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{os.path.basename(contract.pdf_filename)}"'},
    )


# ── 管理者：契約書一覧 ─────────────────────────────────────────────────────────
@app.get("/admin/contracts", response_class=HTMLResponse)
async def admin_contracts(
    request:   Request,
    q:         str = "",
    store_id:  int = 0,
    page:      int = 1,
    store: Store = Depends(require_admin),
    db: Session  = Depends(get_db),
):
    query = db.query(Contract).filter(Contract.is_deleted == False)
    if store_id:
        query = query.filter(Contract.store_id == store_id)
    total   = query.count()
    limit   = 20
    offset  = (page - 1) * limit
    contracts = query.order_by(Contract.submitted_at.desc()).offset(offset).limit(limit).all()
    stores    = db.query(Store).filter(Store.is_admin == False).all()
    return templates.TemplateResponse("admin/contracts.html", {
        "request":   request,
        "store":     store,
        "contracts": contracts,
        "stores":    stores,
        "q":         q,
        "sel_store": store_id,
        "total":     total,
        "page":      page,
        "pages":     (total + limit - 1) // limit,
    })


@app.get("/admin/contracts/download-zip")
async def download_contracts_zip(
    store_id: int = 0,
    store: Store = Depends(require_admin),
    db: Session  = Depends(get_db),
):
    query = db.query(Contract).filter(Contract.is_deleted == False, Contract.pdf_filename != None)
    if store_id:
        query = query.filter(Contract.store_id == store_id)
    contracts = query.all()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for c in contracts:
            if c.pdf_data:
                name = os.path.basename(c.pdf_filename) if c.pdf_filename else f"contract_{c.id}.pdf"
                zf.writestr(name, c.pdf_data)
    buf.seek(0)
    fname = f"contracts_{datetime.now().strftime('%Y%m%d')}.zip"
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


# ── トップ → ログインへリダイレクト ───────────────────────────────────────────
@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    s = get_current_store(request, db)
    if s:
        return RedirectResponse("/admin" if s.is_admin else "/receipt")
    return RedirectResponse("/login")

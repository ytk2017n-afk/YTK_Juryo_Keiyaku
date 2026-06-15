from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
import os

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # PostgreSQL (Supabase) — replace postgres:// with postgresql:// for SQLAlchemy
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    DB_PATH = os.path.join(BASE_DIR, "data", "receipts.db")
    engine  = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()


class Store(Base):
    __tablename__ = "stores"

    id            = Column(Integer, primary_key=True, index=True)
    login_id      = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    store_name    = Column(String(128), nullable=False)       # 発行者：店舗名
    store_address = Column(String(256), nullable=True)        # 発行者：住所
    store_contact = Column(String(128), nullable=True)        # 発行者：連絡先
    invoice_no    = Column(String(20),  nullable=True)        # 発行者：インボイス登録番号
    plain_password = Column(String(256), nullable=True)
    is_admin      = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    receipts  = relationship("Receipt",  back_populates="store")
    contracts = relationship("Contract", back_populates="store")


class Receipt(Base):
    __tablename__ = "receipts"

    id            = Column(Integer, primary_key=True, index=True)
    store_id      = Column(Integer, ForeignKey("stores.id"), nullable=False)

    # ── 基本情報
    receipt_date  = Column(String(20),  nullable=True)   # 日付（手書き→テキスト）
    invoice_no    = Column(String(20),  nullable=True)   # インボイス番号
    shop_name     = Column(String(128), nullable=True)   # 宛名・店舗名

    # ── 受取人情報
    name_alias    = Column(String(64),  nullable=True)   # 源氏名
    name_real     = Column(String(64),  nullable=True)   # 本名
    address       = Column(Text,        nullable=True)   # 住所

    # ── 金額
    amount        = Column(String(32),  nullable=True)   # 金額（文字列で保持）
    tax_amount    = Column(String(32),  nullable=True)   # 消費税額
    total_amount  = Column(String(32),  nullable=True)   # 合計金額

    # ── 但し書
    description   = Column(Text,        nullable=True)

    # ── 署名（Base64 PNG）
    signature_b64 = Column(Text,        nullable=True)

    # ── メタ
    pdf_filename  = Column(String(256), nullable=True)
    pdf_data      = Column(LargeBinary, nullable=True)
    submitted_at  = Column(DateTime,    default=lambda: datetime.now(timezone.utc))
    is_deleted    = Column(Boolean,     default=False)

    store = relationship("Store", back_populates="receipts")


class Contract(Base):
    __tablename__ = "contracts"

    id               = Column(Integer, primary_key=True, index=True)
    store_id         = Column(Integer, ForeignKey("stores.id"), nullable=False)

    # 乙の手書き画像（Base64 PNG）
    oto_preamble_b64 = Column(Text, nullable=True)   # 前文の乙の名前
    date_b64         = Column(Text, nullable=True)   # 日付
    oto_addr_b64     = Column(Text, nullable=True)   # 乙の住所
    oto_realname_b64 = Column(Text, nullable=True)   # 本名
    oto_alias_b64    = Column(Text, nullable=True)   # 源氏名

    pdf_filename = Column(String(256), nullable=True)
    pdf_data     = Column(LargeBinary, nullable=True)
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted   = Column(Boolean, default=False)

    store = relationship("Store", back_populates="contracts")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    if not DATABASE_URL:
        os.makedirs(os.path.join(BASE_DIR, "data", "pdfs"), exist_ok=True)
    Base.metadata.create_all(bind=engine)

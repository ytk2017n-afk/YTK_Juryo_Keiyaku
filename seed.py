"""初期データ投入スクリプト - 最初に一度だけ実行する"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, SessionLocal, Store
from passlib.context import CryptContext

init_db()
pwd = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
db  = SessionLocal()

# 既存チェック
if db.query(Store).count() > 0:
    print("既にデータが存在します。シードをスキップします。")
    print("強制再作成する場合は data/receipts.db を削除してから再実行してください。")
    db.close()
    sys.exit(0)

stores = [
    # YTK 管理者アカウント
    Store(login_id="ytk_admin", password_hash=pwd.hash("admin1234"),
          store_name="YTK管理者", is_admin=True, is_active=True),

    # サンプル店舗1
    Store(login_id="store01", password_hash=pwd.hash("pass0001"),
          store_name="サンプルクラブA",
          store_address="東京都渋谷区〇〇1-2-3",
          store_contact="03-0000-0001",
          invoice_no="1234567890123"),

    # サンプル店舗2
    Store(login_id="store02", password_hash=pwd.hash("pass0002"),
          store_name="サンプルクラブB",
          store_address="東京都新宿区〇〇4-5-6",
          store_contact="03-0000-0002",
          invoice_no="9876543210987"),
]

db.add_all(stores)
db.commit()
db.close()

print("✅ 初期データを投入しました。")
print()
print("─── 管理者アカウント ───────────────────────────")
print("  ログインID : ytk_admin")
print("  パスワード : admin1234")
print()
print("─── サンプル店舗アカウント ─────────────────────")
print("  store01 / pass0001  → サンプルクラブA")
print("  store02 / pass0002  → サンプルクラブB")
print()
print("⚠️  本番環境ではパスワードを必ず変更してください。")

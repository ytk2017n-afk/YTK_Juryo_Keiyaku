# 受領書管理システム

YTK向け 受領書Webアプリ。iPad（Safari + Apple Pencil）対応。

## 機能一覧

| 対象 | 機能 |
|---|---|
| 女の子（店舗スタッフ） | 受領書フォーム入力・Apple Pencil署名・PDF提出 |
| YTK管理者 | 受領書一覧・検索・PDF一括DL・CSV出力・店舗マスタ管理 |

## ファイル構成

```
app/
├── main.py            # FastAPI ルーティング・認証
├── database.py        # SQLAlchemy モデル（Store, Receipt）
├── pdf_generator.py   # reportlab PDF生成
├── seed.py            # 初期データ投入（初回のみ実行）
├── requirements.txt
├── static/
│   ├── css/style.css  # iPad最適化スタイル
│   └── js/receipt.js  # 消費税計算・署名Canvas
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── receipt_form.html
│   ├── receipt_complete.html
│   └── admin/
│       ├── dashboard.html
│       ├── receipts.html
│       └── stores.html
└── data/
    ├── receipts.db    # SQLite DB（自動生成）
    └── pdfs/          # 生成PDF保存先
```

## セットアップ手順

```bash
# 1. 依存ライブラリをインストール
pip3 install -r requirements.txt

# 2. 初期データ投入（初回のみ）
python3 seed.py

# 3. サーバー起動
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

ブラウザで `http://サーバーIP:8000` を開く。

## デフォルトアカウント

| ログインID | パスワード | 権限 |
|---|---|---|
| `ytk_admin` | `admin1234` | YTK管理者 |
| `store01` | `pass0001` | サンプル店舗A |
| `store02` | `pass0002` | サンプル店舗B |

**⚠️ 本番環境では管理画面から全パスワードを変更してください。**

## iPad での使い方（女の子向け）

1. SafariでサーバーURLを開く
2. 店舗IDとパスワードでログイン
3. 各フィールドをタップして入力（Apple Pencil Scribbleで手書き入力可）
4. 消費税額・合計は金額入力で自動計算
5. 署名欄にApple Pencilで署名
6. 「受領書を提出する」ボタンをタップ
7. PDFが生成されてYTKサーバーに自動保存

## サーバー要件

- Python 3.9+
- ディスク空き 1GB以上（PDF保存用）
- ポート8000（または任意）

## VPS デプロイ例（さくら・ConoHa）

```bash
# systemd サービス登録
sudo nano /etc/systemd/system/receipt-app.service

[Unit]
Description=YTK Receipt App
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/receipt-app
ExecStart=/usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target

sudo systemctl enable receipt-app
sudo systemctl start receipt-app
```

## 環境変数

| 変数 | 説明 | デフォルト |
|---|---|---|
| `SECRET_KEY` | セッション署名キー | 開発用固定値（本番では必ず変更） |
